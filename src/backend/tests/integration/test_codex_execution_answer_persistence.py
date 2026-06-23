from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
    insert_chat_run,
    run_state,
    seed_chat_user,
)
from backend.tests.support.codex import (
    ARTIFACT_SOURCE_PATH,
    FakeAdoptedArtifactStore,
    FakeCodexGenerationRunner,
    FakeReferenceFileValidator,
    FakeRunEventPublisher,
    FakeTraceLogger,
    FakeValidatorCodexRunner,
    ValidatorRunResultRecord,
    artifact_link_candidate_json,
    dangerous_html_candidate_json,
    empty_answers_candidate_json,
    generation_result,
    invalid_reference_candidate_json,
    non_pdf_reference_candidate_json,
    reference_validation_records,
    saved_answer_count,
    saved_artifact_paths,
    valid_candidate_json,
    validation_result,
)
from backend.tests.support.execution import parse_sse_events
from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    create_foundation_config,
    foundation_test_database_url,
    prepare_foundation_database,
)


@pytest.mark.asyncio
async def test_fake_codex_execution_persists_completed_answer_and_rest_sse_payload(
    tmp_path: Path,
) -> None:
    """
    観点：Codex実行、回答検証、採用保存がDB永続化とREST/SSE再表示へ連携すること
    確認：実Codexを起動せずFake応答でrunがcompletedとなり、回答本文、参照元、
    保存済み成果物URLが履歴詳細APIとSSE answer payloadから取得できること
    """
    from backend.app.factory import create_app
    from backend.application.artifacts.save_adopted_artifacts import (
        SaveAdoptedArtifactsUseCase,
    )
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )
    from backend.application.validation.validate_answer import ValidateAnswerUseCase
    from backend.infrastructure.database.repositories.chat import (
        SqlAlchemyChatRepository,
    )
    from backend.infrastructure.database.session.factory import (
        create_database_engine,
        create_session_factory,
    )
    from backend.infrastructure.database.session.transaction_manager import (
        SqlAlchemyTransactionManager,
    )
    from backend.infrastructure.runtime.clock import SystemClock

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("90909090-9090-7090-8090-909090909090"),
        title="F005回答保存チャット",
        instruction="ポンプ点検方法を教えてください。",
        run_state=RunState.ACCEPTED.value,
    )
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            repository = SqlAlchemyChatRepository(session)
            use_case = ExecuteChatRunUseCase(
                repository=repository,
                transaction_manager=SqlAlchemyTransactionManager(session),
                generation_runner=FakeCodexGenerationRunner(
                    results=[
                        generation_result(
                            tmp_path,
                            candidate_json=valid_candidate_json(
                                f"回答本文です。![図]({ARTIFACT_SOURCE_PATH})",
                            ),
                        ),
                    ],
                ),
                answer_validator=ValidateAnswerUseCase(
                    reference_validator=FakeReferenceFileValidator(
                        reference_validation_records(),
                    ),
                    validator_runner=FakeValidatorCodexRunner(
                        results=[validation_result(valid=True)],
                    ),
                ),
                adopted_artifact_saver=SaveAdoptedArtifactsUseCase(
                    artifact_store=FakeAdoptedArtifactStore(),
                ),
                event_publisher=FakeRunEventPublisher(),
                clock=SystemClock("Asia/Tokyo"),
                trace_logger=FakeTraceLogger(),
            )
            use_case.execute(
                ExecuteChatRunCommand(
                    chat_id=CHAT_ID_VALUE,
                    run_id=RUN_ID_VALUE,
                    trace_id="trace-f005",
                ),
            )
    finally:
        engine.dispose()

    assert run_state(database_url, RUN_ID_VALUE) == RunState.COMPLETED.value
    assert saved_answer_count(database_url, RUN_ID_VALUE) == 1
    assert saved_artifact_paths(database_url) == (
        f"{seeded.user_id}/{SESSION_ID_VALUE}/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa.svg",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        detail = await client.get(f"/api/chats/{CHAT_ID_VALUE}")
        sse = await client.get(f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/sse")

    assert detail.status_code == 200
    detail_payload = detail.json()
    completed_run = detail_payload["runs"][0]
    assert completed_run["state"] == RunState.COMPLETED.value
    assert completed_run["answer"]["blocks"][0]["markdown"] == (
        "回答本文です。![図](/api/artifacts/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa)"
    )
    assert completed_run["answer"]["blocks"][0]["references"][0]["locator"] == {
        "page_start": 2,
        "page_end": 3,
    }
    events = parse_sse_events(sse.text)
    assert events[-1].event == "answer"
    answer_reference = events[-1].payload["answer"]["blocks"][0]["references"][0]
    assert answer_reference["source_type"] == "pdf"


@pytest.mark.asyncio
async def test_fake_codex_validation_failure_marks_error_without_answer(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証が再生成上限で失敗した場合のDB整合
    確認：検証不合格が上限へ到達するとrunはerrorへ終端し、回答ブロックと
    成果物メタは保存されず、履歴詳細APIにもanswerが出ないこと
    """
    from backend.app.factory import create_app
    from backend.application.artifacts.save_adopted_artifacts import (
        SaveAdoptedArtifactsUseCase,
    )
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )
    from backend.application.validation.validate_answer import ValidateAnswerUseCase
    from backend.infrastructure.database.repositories.chat import (
        SqlAlchemyChatRepository,
    )
    from backend.infrastructure.database.session.factory import (
        create_database_engine,
        create_session_factory,
    )
    from backend.infrastructure.database.session.transaction_manager import (
        SqlAlchemyTransactionManager,
    )
    from backend.infrastructure.runtime.clock import SystemClock

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url, session_token="f005-error-session")
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("91919191-9191-7191-8191-919191919191"),
        title="F005検証失敗チャット",
        instruction="根拠不足になる回答を作ってください。",
        run_state=RunState.ACCEPTED.value,
    )
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            repository = SqlAlchemyChatRepository(session)
            use_case = ExecuteChatRunUseCase(
                repository=repository,
                transaction_manager=SqlAlchemyTransactionManager(session),
                generation_runner=FakeCodexGenerationRunner(
                    results=[generation_result(tmp_path)],
                ),
                answer_validator=ValidateAnswerUseCase(
                    reference_validator=FakeReferenceFileValidator(
                        reference_validation_records(),
                    ),
                    validator_runner=FakeValidatorCodexRunner(
                        results=[
                            validation_result(
                                valid=False,
                                comment="根拠として十分ではありません。",
                            ),
                        ],
                    ),
                ),
                adopted_artifact_saver=SaveAdoptedArtifactsUseCase(
                    artifact_store=FakeAdoptedArtifactStore(),
                ),
                event_publisher=FakeRunEventPublisher(),
                clock=SystemClock("Asia/Tokyo"),
                trace_logger=FakeTraceLogger(),
                max_regenerations=0,
            )
            use_case.execute(
                ExecuteChatRunCommand(
                    chat_id=CHAT_ID_VALUE,
                    run_id=RUN_ID_VALUE,
                    trace_id="trace-f005",
                ),
            )
    finally:
        engine.dispose()

    assert run_state(database_url, RUN_ID_VALUE) == RunState.ERROR.value
    assert saved_answer_count(database_url, RUN_ID_VALUE) == 0
    assert saved_artifact_paths(database_url) == ()
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        detail = await client.get(f"/api/chats/{CHAT_ID_VALUE}")

    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["runs"][0]["state"] == RunState.ERROR.value
    assert detail_payload["runs"][0]["answer"] is None


@pytest.mark.parametrize(
    ("candidate_json", "diagnostic_fragment"),
    (
        ("[]", "payload.answers"),
        (empty_answers_candidate_json(), "payload.answers"),
        (valid_candidate_json(markdown="   "), "payload.answers[0].text"),
        (invalid_reference_candidate_json(), "../secret.pdf"),
        (non_pdf_reference_candidate_json(), "source_type"),
        (dangerous_html_candidate_json(), "HTML"),
        (
            artifact_link_candidate_json("![図](https://example.test/secret.svg)"),
            "https://example.test/secret.svg",
        ),
        (
            artifact_link_candidate_json("![図](artifacts/script.exe)"),
            "artifacts/script.exe",
        ),
        (
            (
                '{"payload":{"kind":"final","answers":[{"text":"ページ境界を確認します。",'
                '"references":[{"source_type":"pdf","locator":{'
                '"path":"data_source/manuals/pump.pdf","start_page":0,"end_page":1'
                "}}]}]}}"
            ),
            "ページ範囲が不正",
        ),
        (
            (
                '{"payload":{"kind":"final","answers":[{"text":"ページ境界を確認します。",'
                '"references":[{"source_type":"pdf","locator":{'
                '"path":"data_source/manuals/pump.pdf","start_page":7,"end_page":9'
                "}}]}]}}"
            ),
            "PDFページ数を超えています",
        ),
    ),
)
def test_validate_answer_integration_rejects_fixed_validation_boundaries(
    tmp_path: Path,
    candidate_json: str,
    diagnostic_fragment: str,
) -> None:
    """
    観点：固定回答検証がDB永続化前の候補JSONと成果物境界を遮断すること
    確認：構造不備、参照元不備、許可外成果物リンクでは検証用Codexを呼ばず、
    再生成指示に診断を含めること
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
        ValidationStatus,
    )

    validator_runner = FakeValidatorCodexRunner(results=[validation_result(valid=True)])
    use_case = ValidateAnswerUseCase(
        reference_validator=FakeReferenceFileValidator(reference_validation_records()),
        validator_runner=validator_runner,
    )

    result = use_case.execute(
        ValidateAnswerCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id="f005-user",
            session_id=SESSION_ID_VALUE,
            candidate_json=candidate_json,
            artifacts_dir=tmp_path,
            retry_count=0,
            max_regenerations=2,
            remaining_seconds=300,
            trace_id="trace-f005",
        ),
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.answer is None
    assert result.regeneration_instruction is not None
    assert diagnostic_fragment in result.regeneration_instruction
    assert validator_runner.requests == []


def test_validate_answer_integration_regenerates_when_pdf_reference_file_is_missing(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証が参照元PDFの実ファイル境界と再生成判定を結合すること
    確認：共有データソース内にPDFが存在しない場合はSYSTEM障害にせず、
    検証用Codexを呼ばずにREGENERATEと不正参照元の指摘を返すこと
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
        ValidationStatus,
    )
    from backend.infrastructure.filesystem.reference_file_validator import (
        PdfReferenceFileValidator,
    )

    data_source_dir = tmp_path / "data_source"
    data_source_dir.mkdir()
    validator_runner = FakeValidatorCodexRunner(results=[validation_result(valid=True)])
    use_case = ValidateAnswerUseCase(
        reference_validator=PdfReferenceFileValidator(data_source_dir=data_source_dir),
        validator_runner=validator_runner,
    )

    result = use_case.execute(
        ValidateAnswerCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id="f005-user",
            session_id=SESSION_ID_VALUE,
            candidate_json=valid_candidate_json(markdown="回答本文"),
            artifacts_dir=tmp_path,
            retry_count=0,
            max_regenerations=2,
            remaining_seconds=300,
            trace_id="trace-f005",
        ),
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.answer is None
    assert result.regeneration_instruction is not None
    assert "manuals/pump.pdf" in result.regeneration_instruction
    assert validator_runner.requests == []


def test_validate_answer_integration_raises_when_validator_output_is_invalid(
    tmp_path: Path,
) -> None:
    """
    観点：検証用Codexの出力契約違反を回答採用へ進めないこと
    確認：再出力後もfinal/valid/commentを満たさない場合はSYSTEMかつtrace対象の
    AppErrorとなり、同じ検証会話をresumeすること
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
    )

    validator_runner = FakeValidatorCodexRunner(
        results=[
            ValidatorRunResultRecord(
                conversation_id="validator-thread-001",
                progress_messages=("形式確認中です。",),
                final_result_json='{"payload":{"kind":"progress","text":"途中"}}',
            ),
            ValidatorRunResultRecord(
                conversation_id="validator-thread-002",
                progress_messages=("再確認中です。",),
                final_result_json='{"payload":{"kind":"final","valid":"yes","comment":""}}',
            ),
        ],
    )
    use_case = ValidateAnswerUseCase(
        reference_validator=FakeReferenceFileValidator(reference_validation_records()),
        validator_runner=validator_runner,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            ValidateAnswerCommand(
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                user_id="f005-user",
                session_id=SESSION_ID_VALUE,
                candidate_json=valid_candidate_json(markdown="回答本文"),
                artifacts_dir=tmp_path,
                retry_count=0,
                max_regenerations=2,
                remaining_seconds=300,
                trace_id="trace-f005",
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert validator_runner.requests[1].resume_conversation_id == "validator-thread-001"


@pytest.mark.parametrize(
    "markdown",
    (
        "![図](../secret.svg)",
        "![図](/absolute/secret.svg)",
        "![図](artifacts/script.exe)",
        "![図](artifacts/missing.svg)",
    ),
)
def test_save_adopted_artifacts_integration_rejects_unsafe_candidates(
    tmp_path: Path,
    markdown: str,
) -> None:
    """
    観点：採用済み成果物保存が生成作業領域の安全な候補だけをDB保存対象にすること
    確認：親ディレクトリ、絶対パス、許可外拡張子、存在しないファイルは
    trace対象AppErrorとなり、保存境界を呼ばないこと
    """
    from backend.application.artifacts.save_adopted_artifacts import (
        SaveAdoptedArtifactsCommand,
        SaveAdoptedArtifactsUseCase,
    )

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    store = FakeAdoptedArtifactStore()
    use_case = SaveAdoptedArtifactsUseCase(artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            SaveAdoptedArtifactsCommand(
                user_id="f005-user",
                session_id=SESSION_ID_VALUE,
                artifacts_dir=artifacts_dir,
                markdown_blocks=(markdown,),
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert store.saved == []

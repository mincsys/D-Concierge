from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    F003_USER_ID,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
)
from backend.tests.support.codex import (
    ARTIFACT_SOURCE_PATH,
    REFERENCE_PATH,
    FakeReferenceFileValidator,
    FakeValidatorCodexRunner,
    artifact_link_candidate_json,
    dangerous_html_candidate_json,
    empty_answers_candidate_json,
    invalid_reference_candidate_json,
    non_pdf_reference_candidate_json,
    reference_validation_records,
    valid_candidate_json,
    validation_result,
)


@dataclass(frozen=True, slots=True)
class FixedValidationFailureCase:
    name: str
    candidate_json: str
    diagnostic_fragment: str


def test_validate_answer_accepts_normalized_pdf_reference_and_artifact_link(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースが固定検証とCodex検証の合格結果を統合すること
    確認：data_source接頭辞とstart_page/end_pageを内部形式へ正規化し、
    成果物リンクがある場合は検証用Codexへartifactsディレクトリを渡すこと
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
        ValidationStatus,
    )

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "diagram.svg").write_text("<svg />", encoding="utf-8")
    (artifacts_dir / "report.html").write_text("<!doctype html>", encoding="utf-8")
    validator_runner = FakeValidatorCodexRunner(results=[validation_result(valid=True)])
    use_case = ValidateAnswerUseCase(
        reference_validator=FakeReferenceFileValidator(reference_validation_records()),
        validator_runner=validator_runner,
    )

    result = use_case.execute(
        ValidateAnswerCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=valid_candidate_json(
                markdown=(
                    f"ポンプは定期点検が必要です。![図]({ARTIFACT_SOURCE_PATH})"
                    ' <a href="artifacts/report.html">HTML</a>'
                ),
            ),
            artifacts_dir=artifacts_dir,
            retry_count=0,
            max_regenerations=2,
            remaining_seconds=480,
            trace_id="trace-f005",
        ),
    )

    assert result.status is ValidationStatus.ACCEPTED
    assert result.regeneration_instruction is None
    assert result.answer is not None
    assert result.answer.blocks[0].markdown.startswith("ポンプは定期点検")
    reference = result.answer.blocks[0].references[0]
    assert reference.source_type == "pdf"
    assert reference.path == REFERENCE_PATH
    assert reference.page_start == 2
    assert reference.page_end == 3
    assert result.answer.blocks[0].artifact_links == (
        ARTIFACT_SOURCE_PATH,
        "artifacts/report.html",
    )
    assert validator_runner.requests[0].user_id == F003_USER_ID
    assert validator_runner.requests[0].remaining_seconds == 480
    assert validator_runner.requests[0].artifacts_readonly_dir == artifacts_dir


def test_validate_answer_rejects_fixed_validation_error_before_codex_validation(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースが固定検証で明確な不備を検出すること
    確認：不正な参照元パスとページ範囲ではCodex検証を呼ばず、再生成指示に
    payload.answers[n].references[m] の位置情報を含めること
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
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=invalid_reference_candidate_json(),
            artifacts_dir=tmp_path,
            retry_count=0,
            max_regenerations=2,
            remaining_seconds=480,
            trace_id="trace-f005",
        ),
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.answer is None
    assert validator_runner.requests == []
    assert result.regeneration_instruction is not None
    assert "不合格理由" in result.regeneration_instruction
    assert "payload.answers[0].references[0]" in result.regeneration_instruction
    assert "../secret.pdf" in result.regeneration_instruction


@pytest.mark.parametrize(
    "case",
    (
        FixedValidationFailureCase(
            name="empty_answers",
            candidate_json=empty_answers_candidate_json(),
            diagnostic_fragment="payload.answers",
        ),
        FixedValidationFailureCase(
            name="empty_answer_text",
            candidate_json=valid_candidate_json(markdown="  "),
            diagnostic_fragment="payload.answers[0].text",
        ),
        FixedValidationFailureCase(
            name="non_pdf_reference",
            candidate_json=non_pdf_reference_candidate_json(),
            diagnostic_fragment="source_type",
        ),
        FixedValidationFailureCase(
            name="dangerous_html",
            candidate_json=dangerous_html_candidate_json(),
            diagnostic_fragment="HTML",
        ),
        FixedValidationFailureCase(
            name="artifact_parent_directory",
            candidate_json=artifact_link_candidate_json("![図](../secret.svg)"),
            diagnostic_fragment="../secret.svg",
        ),
        FixedValidationFailureCase(
            name="artifact_absolute_path",
            candidate_json=artifact_link_candidate_json("![図](/tmp/secret.svg)"),
            diagnostic_fragment="/tmp/secret.svg",
        ),
        FixedValidationFailureCase(
            name="artifact_url",
            candidate_json=artifact_link_candidate_json(
                "![図](https://example.test/secret.svg)",
            ),
            diagnostic_fragment="https://example.test/secret.svg",
        ),
        FixedValidationFailureCase(
            name="artifact_disallowed_extension",
            candidate_json=artifact_link_candidate_json("![図](artifacts/run.sh)"),
            diagnostic_fragment="artifacts/run.sh",
        ),
        FixedValidationFailureCase(
            name="artifact_image_disallowed_html",
            candidate_json=artifact_link_candidate_json("![図](artifacts/report.html)"),
            diagnostic_fragment="artifacts/report.html",
        ),
        FixedValidationFailureCase(
            name="artifact_link_disallowed_gif",
            candidate_json=artifact_link_candidate_json(
                "[詳細](artifacts/diagram.gif)"
            ),
            diagnostic_fragment="artifacts/diagram.gif",
        ),
        FixedValidationFailureCase(
            name="artifact_missing_file",
            candidate_json=artifact_link_candidate_json("![図](artifacts/missing.svg)"),
            diagnostic_fragment="artifacts/missing.svg",
        ),
    ),
    ids=lambda case: case.name,
)
def test_validate_answer_rejects_fixed_validation_failures_before_codex(
    tmp_path: Path,
    case: FixedValidationFailureCase,
) -> None:
    """
    観点：回答検証ユースケースが固定検証の異常系をCodex検証前に遮断すること
    確認：空回答、非PDF参照元、危険HTML、不正成果物リンクでは
    ValidatorCodexRunnerを呼ばず、再生成指示に原因を含めること
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
        ValidationStatus,
    )

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "diagram.svg").write_text("<svg />", encoding="utf-8")
    validator_runner = FakeValidatorCodexRunner(results=[validation_result(valid=True)])
    use_case = ValidateAnswerUseCase(
        reference_validator=FakeReferenceFileValidator(reference_validation_records()),
        validator_runner=validator_runner,
    )

    result = use_case.execute(
        ValidateAnswerCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=case.candidate_json,
            artifacts_dir=artifacts_dir,
            retry_count=0,
            max_regenerations=2,
            remaining_seconds=480,
            trace_id="trace-f005",
        ),
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.answer is None
    assert validator_runner.requests == []
    assert result.regeneration_instruction is not None
    assert "不合格理由" in result.regeneration_instruction
    assert case.diagnostic_fragment in result.regeneration_instruction


def test_validate_answer_retries_invalid_validator_output_then_accepts(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースが検証用Codexの出力形式不備を再出力で回復すること
    確認：final形式でない検証結果を同じ検証会話の再出力対象とし、
    再出力後のvalid=trueで採用可能結果にすること
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
        ValidationStatus,
    )
    from backend.tests.support.codex import ValidatorRunResultRecord

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    validator_runner = FakeValidatorCodexRunner(
        results=[
            ValidatorRunResultRecord(
                conversation_id="validator-thread-001",
                progress_messages=("形式を確認しています。",),
                final_result_json='{"payload":{"kind":"progress","text":"途中"}}',
            ),
            validation_result(valid=True),
        ],
    )
    use_case = ValidateAnswerUseCase(
        reference_validator=FakeReferenceFileValidator(reference_validation_records()),
        validator_runner=validator_runner,
    )

    result = use_case.execute(
        ValidateAnswerCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=valid_candidate_json(markdown="回答本文"),
            artifacts_dir=artifacts_dir,
            retry_count=0,
            max_regenerations=2,
            remaining_seconds=300,
            trace_id="trace-f005",
        ),
    )

    assert result.status is ValidationStatus.ACCEPTED
    assert len(validator_runner.requests) == 2
    assert validator_runner.requests[1].resume_conversation_id == "validator-thread-001"


def test_validate_answer_returns_regeneration_or_failed_by_retry_count(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースが検証不合格と再生成上限を区別すること
    確認：再生成可能ならREGENERATEと修正指示、上限到達ならFAILEDとなり、
    採用済み回答を返さないこと
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
        ValidationStatus,
    )

    use_case = ValidateAnswerUseCase(
        reference_validator=FakeReferenceFileValidator(reference_validation_records()),
        validator_runner=FakeValidatorCodexRunner(
            results=[
                validation_result(valid=False, comment="根拠ページが不足しています。"),
                validation_result(valid=False, comment="根拠ページが不足しています。"),
            ],
        ),
    )

    regenerate = use_case.execute(
        ValidateAnswerCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=valid_candidate_json(markdown="回答本文"),
            artifacts_dir=tmp_path,
            retry_count=0,
            max_regenerations=1,
            remaining_seconds=300,
            trace_id="trace-f005",
        ),
    )
    failed = use_case.execute(
        ValidateAnswerCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            candidate_json=valid_candidate_json(markdown="回答本文"),
            artifacts_dir=tmp_path,
            retry_count=1,
            max_regenerations=1,
            remaining_seconds=300,
            trace_id="trace-f005",
        ),
    )

    assert regenerate.status is ValidationStatus.REGENERATE
    assert regenerate.regeneration_instruction is not None
    assert "根拠ページが不足しています。" in regenerate.regeneration_instruction
    assert failed.status is ValidationStatus.FAILED
    assert failed.answer is None
    assert failed.diagnostic_message == "根拠ページが不足しています。"


def test_validate_answer_raises_system_error_when_pdf_is_unreadable(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースがPDF参照元の読込不能を再生成ではなく障害として扱うこと
    確認：ReferenceFileValidatorが読込不能を返す場合、SYSTEMかつtrace対象の
    AppErrorとなり、検証用Codexを呼ばないこと
    """
    from backend.application.ports.codex.dto import ReferenceValidationResult
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
    )

    validator_runner = FakeValidatorCodexRunner(results=[validation_result(valid=True)])
    use_case = ValidateAnswerUseCase(
        reference_validator=FakeReferenceFileValidator(
            records={
                REFERENCE_PATH: ReferenceValidationResult(
                    path=REFERENCE_PATH,
                    page_start=2,
                    page_end=3,
                    exists=True,
                    readable=False,
                    page_count=0,
                ),
            },
        ),
        validator_runner=validator_runner,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            ValidateAnswerCommand(
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                user_id=F003_USER_ID,
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
    assert REFERENCE_PATH in raised.value.diagnostic_message
    assert validator_runner.requests == []


def test_validate_answer_regenerates_when_pdf_reference_file_is_missing(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースが参照元PDFの不存在を再生成可能な回答不備として扱うこと
    確認：実ファイル境界でPDFが存在しない場合はSYSTEM障害にせず、
    検証用Codexを呼ばずにREGENERATEと再生成指示を返すこと
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
            user_id=F003_USER_ID,
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
    assert REFERENCE_PATH in result.regeneration_instruction
    assert validator_runner.requests == []


def test_validate_answer_raises_system_error_when_existing_pdf_is_unreadable(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースが存在するPDFの読込不能をシステム障害として扱うこと
    確認：実ファイル境界でPDFファイルが存在するのに読み取れない場合だけ、
    SYSTEMかつtrace対象のAppErrorとなること
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
    )
    from backend.infrastructure.filesystem.reference_file_validator import (
        PdfReferenceFileValidator,
    )

    data_source_dir = tmp_path / "data_source"
    manuals_dir = data_source_dir / "manuals"
    manuals_dir.mkdir(parents=True)
    (manuals_dir / "pump.pdf").write_text("not a pdf", encoding="utf-8")
    validator_runner = FakeValidatorCodexRunner(results=[validation_result(valid=True)])
    use_case = ValidateAnswerUseCase(
        reference_validator=PdfReferenceFileValidator(data_source_dir=data_source_dir),
        validator_runner=validator_runner,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            ValidateAnswerCommand(
                chat_id=CHAT_ID_VALUE,
                run_id=RUN_ID_VALUE,
                user_id=F003_USER_ID,
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
    assert REFERENCE_PATH in raised.value.diagnostic_message
    assert validator_runner.requests == []


@pytest.mark.parametrize(
    "candidate_json",
    (
        "[]",
        '{"payload":[]}',
        '{"payload":{"kind":"progress","answers":[]}}',
        '{"payload":{"kind":"final","answers":"本文"}}',
        '{"payload":{"kind":"final","answers":[[]]}}',
        '{"payload":{"kind":"final","answers":[{"text":1,"references":[]}]}}',
        '{"payload":{"kind":"final","answers":[{"text":"本文","references":"根拠"}]}}',
        ('{"payload":{"kind":"final","answers":[{"text":"本文","references":[[]]}]}}'),
        (
            '{"payload":{"kind":"final","answers":[{"text":"本文",'
            '"references":[{"source_type":"pdf","locator":[]}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"本文",'
            '"references":[{"source_type":"pdf","locator":{'
            '"path":1,"start_page":1,"end_page":1}}]}]}}'
        ),
        (
            '{"payload":{"kind":"final","answers":[{"text":"本文",'
            '"references":[{"source_type":"pdf","locator":{'
            '"path":"data_source/manuals/pump.pdf","start_page":true,'
            '"end_page":1}}]}]}}'
        ),
    ),
)
def test_validate_answer_rejects_malformed_candidate_payload_before_codex(
    tmp_path: Path,
    candidate_json: str,
) -> None:
    """
    観点：回答検証ユースケースが候補JSONの構造不備を固定検証で遮断すること
    確認：payload、answers、reference、locatorの型不備では検証用Codexを呼ばず、
    再生成指示を返すこと
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
            user_id=F003_USER_ID,
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
    assert "payload.answers" in result.regeneration_instruction
    assert validator_runner.requests == []


def test_validate_answer_rejects_invalid_page_range_and_page_count(
    tmp_path: Path,
) -> None:
    """
    観点：回答検証ユースケースがPDF参照元のページ境界を検証すること
    確認：開始ページ0、終了ページが開始ページ未満、PDFページ数超過は
    検証用Codexを呼ばず、再生成指示へ該当診断を含めること
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
        ValidationStatus,
    )

    candidate_json = (
        '{"payload":{"kind":"final","answers":[{"text":"ページ境界を確認します。",'
        '"references":[{"source_type":"pdf","locator":{'
        f'"path":"data_source/{REFERENCE_PATH}","start_page":0,"end_page":1'
        '}},{"source_type":"pdf","locator":{'
        f'"path":"data_source/{REFERENCE_PATH}","start_page":4,"end_page":3'
        '}},{"source_type":"pdf","locator":{'
        f'"path":"data_source/{REFERENCE_PATH}","start_page":7,"end_page":9'
        "}}]}]}}"
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
            user_id=F003_USER_ID,
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
    assert result.regeneration_instruction is not None
    assert "ページ範囲が不正" in result.regeneration_instruction
    assert "PDFページ数を超えています" in result.regeneration_instruction
    assert validator_runner.requests == []


@pytest.mark.parametrize(
    "final_result_json",
    (
        "[]",
        '{"payload":[]}',
        '{"payload":{"kind":"progress","valid":true,"comment":""}}',
        '{"payload":{"kind":"final","valid":"true","comment":""}}',
        '{"payload":{"kind":"final","valid":true,"comment":1}}',
    ),
)
def test_validate_answer_raises_when_validator_output_never_becomes_final(
    tmp_path: Path,
    final_result_json: str,
) -> None:
    """
    観点：回答検証ユースケースが検証用Codexの不正出力を障害として扱うこと
    確認：再出力してもfinal/valid/comment契約を満たさない場合はSYSTEMかつ
    trace対象のAppErrorとなること
    """
    from backend.application.validation.validate_answer import (
        ValidateAnswerCommand,
        ValidateAnswerUseCase,
    )
    from backend.tests.support.codex import ValidatorRunResultRecord

    validator_runner = FakeValidatorCodexRunner(
        results=[
            ValidatorRunResultRecord(
                conversation_id="validator-thread-001",
                progress_messages=(),
                final_result_json=final_result_json,
            ),
            ValidatorRunResultRecord(
                conversation_id="validator-thread-002",
                progress_messages=(),
                final_result_json=final_result_json,
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
                user_id=F003_USER_ID,
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
    assert "検証用Codex" in raised.value.diagnostic_message
    assert len(validator_runner.requests) == 2

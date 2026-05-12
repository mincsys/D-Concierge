from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from backend.application.artifacts.save_adopted_artifacts import (
    SavedAnswerBlockArtifacts,
    SavedAnswerBlocksArtifacts,
)
from backend.application.execution.execute_chat_run import (
    AdoptedArtifactSaver,
    AnswerValidator,
    RunEvent,
    RunEventPublisher,
)
from backend.application.execution.execute_chat_run import (
    ExecuteChatRunUseCase as _ExecuteChatRunUseCase,
)
from backend.application.execution.run_event_type import RunEventType
from backend.application.ports.codex.dto import CodexRunResult
from backend.application.ports.codex.interface import (
    CodexGenerationRunnerPort,
    SessionWorkdirResolverPort,
)
from backend.application.ports.database.interface import (
    ChatExecutionRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import ClockPort, IdGeneratorPort
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.ports.trace_log.interface import TraceLoggerPort
from backend.application.validation.validate_answer import AnswerValidationResult
from backend.application.validation.validation_status import ValidationStatus
from backend.domain.answer.answer_candidate import (
    AnswerParseError,
    ParsedAnswerBlock,
    ParsedAnswerCandidate,
    parse_generation_final_output,
)
from backend.domain.artifacts.artifact_reference import ArtifactReference
from backend.domain.execution.run_state import RunState
from backend.domain.references.pdf_reference import PdfLocator, PdfReference
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import (
    AppError,
    ReferencePdfReadError,
    RunTimeoutError,
    ValidationResultFormatError,
)
from backend.tests.support.memory_repository import InMemoryChatRepository


def ExecuteChatRunUseCase(
    *,
    repository: ChatExecutionRepositoryPort,
    codex_runner: CodexGenerationRunnerPort,
    answer_validator: AnswerValidator,
    event_publisher: RunEventPublisher,
    clock: ClockPort | None = None,
    id_generator: IdGeneratorPort | None = None,
    artifact_saver: AdoptedArtifactSaver | None = None,
    session_workdir: Path | None = None,
    session_workdir_resolver: SessionWorkdirResolverPort | None = None,
    trace_logger: TraceLoggerPort | None = None,
    timeout_seconds: int = 300,
    transaction_manager: TransactionManagerPort | None = None,
) -> _ExecuteChatRunUseCase:
    """テスト用既定Runtime境界を補ってUseCaseを生成する。"""
    runtime_clock = clock or SequenceClock((datetime(2026, 5, 9, 10, 0, tzinfo=UTC),))
    runtime_id_generator = id_generator or SequenceIdGenerator()
    return _ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=codex_runner,
        answer_validator=answer_validator,
        event_publisher=event_publisher,
        clock=runtime_clock,
        id_generator=runtime_id_generator,
        artifact_saver=artifact_saver,
        session_workdir=session_workdir,
        session_workdir_resolver=session_workdir_resolver,
        trace_logger=trace_logger,
        timeout_seconds=timeout_seconds,
        transaction_manager=transaction_manager,
    )


def test_execute_chat_run_saves_verified_answer_and_publishes_events() -> None:
    """観点：チャット実行処理。

    確認：生成結果を検証済み回答として保存し、状態、中間、回答イベントを発行する。
    """
    repository = InMemoryChatRepository(
        now_values=(
            datetime(2026, 5, 9, 10, 0, tzinfo=UTC),
            datetime(2026, 5, 9, 10, 1, tzinfo=UTC),
            datetime(2026, 5, 9, 10, 2, tzinfo=UTC),
        )
    )
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=("資料を検索しています。",),
                    final_answer_json=_valid_answer_json(),
                ),
            )
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id)

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.COMPLETED
    assert detail.runs[0].answer is not None
    assert detail.runs[0].answer.blocks[0].markdown == "要点はAです。"
    assert detail.runs[0].answer.blocks[0].references[0].relative_path == "manual.pdf"
    assert detail.runs[0].answer.blocks[0].references[0].page_start == 2
    assert [message.text for message in detail.runs[0].intermediate_messages] == [
        "作業を開始します。",
        "資料を検索しています。",
        "作業が完了しました。",
        "回答を検証します。",
        "回答を検証しました。",
    ]
    assert [(event.event, event.text) for event in publisher.events] == [
        (RunEventType.STATE, None),
        (RunEventType.MESSAGE, "作業を開始します。"),
        (RunEventType.MESSAGE, "資料を検索しています。"),
        (RunEventType.MESSAGE, "作業が完了しました。"),
        (RunEventType.STATE, None),
        (RunEventType.MESSAGE, "回答を検証します。"),
        (RunEventType.MESSAGE, "回答を検証しました。"),
        (RunEventType.ANSWER, None),
    ]


def test_execute_chat_run_merges_reference_ranges_before_save() -> None:
    """観点：検証済み回答保存。

    確認：DB保存前に参照元をパス順とページ順へ並べ、重複・隣接範囲を結合する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json='{"payload":{"kind":"final","answers":[]}}',
                ),
            )
        ),
        answer_validator=QueuedAnswerValidator(
            results=(
                AnswerValidationResult(
                    status=ValidationStatus.ACCEPTED,
                    candidate=ParsedAnswerCandidate(
                        blocks=(
                            ParsedAnswerBlock(
                                markdown="回答",
                                references=(
                                    _pdf_reference(
                                        label="b.pdf",
                                        relative_path="b.pdf",
                                        page_start=5,
                                        page_end=5,
                                    ),
                                    _pdf_reference(
                                        label="a.pdf",
                                        relative_path="a.pdf",
                                        page_start=3,
                                        page_end=4,
                                    ),
                                    _pdf_reference(
                                        label="a.pdf",
                                        relative_path="a.pdf",
                                        page_start=1,
                                        page_end=2,
                                    ),
                                    _pdf_reference(
                                        label="a.pdf",
                                        relative_path="a.pdf",
                                        page_start=5,
                                        page_end=6,
                                    ),
                                    _pdf_reference(
                                        label="b.pdf",
                                        relative_path="b.pdf",
                                        page_start=1,
                                        page_end=2,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            )
        ),
        event_publisher=RecordingPublisher(),
    )

    use_case.execute(accepted.chat_id, accepted.run_id)

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].answer is not None
    assert [
        (reference.relative_path, reference.page_start, reference.page_end)
        for reference in detail.runs[0].answer.blocks[0].references
    ] == [
        ("a.pdf", 1, 6),
        ("b.pdf", 1, 2),
        ("b.pdf", 5, 5),
    ]


def test_execute_chat_run_publishes_streamed_intermediate_message_before_return() -> (
    None
):
    """観点：チャット実行処理の中間メッセージ逐次配信。

    確認：生成実行中に通知された中間メッセージを、生成完了を待たずに保存・配信する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    runner = StreamingFakeCodexRunner(repository=repository, publisher=publisher)
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id)

    assert runner.start_message_was_persisted_before_generation
    assert runner.message_was_persisted_before_return
    assert runner.message_was_published_before_return
    assert [(event.event, event.text) for event in publisher.events] == [
        (RunEventType.STATE, None),
        (RunEventType.MESSAGE, "作業を開始します。"),
        (RunEventType.MESSAGE, "資料を確認しています。"),
        (RunEventType.MESSAGE, "作業が完了しました。"),
        (RunEventType.STATE, None),
        (RunEventType.MESSAGE, "回答を検証します。"),
        (RunEventType.MESSAGE, "回答を検証しました。"),
        (RunEventType.ANSWER, None),
    ]


def test_execute_chat_run_publishes_validation_intermediate_message() -> None:
    """観点：チャット実行処理の検証中間メッセージ配信。

    確認：検証用Codexから通知された中間メッセージを保存しSSE配信する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json=_valid_answer_json(),
                ),
            )
        ),
        answer_validator=ValidationStreamingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id)

    detail = repository.get_chat_detail(accepted.chat_id)
    assert [message.text for message in detail.runs[0].intermediate_messages] == [
        "作業を開始します。",
        "作業が完了しました。",
        "回答を検証します。",
        "参照元PDFを検証しています。",
        "回答を検証しました。",
    ]
    assert [(event.event, event.text) for event in publisher.events] == [
        (RunEventType.STATE, None),
        (RunEventType.MESSAGE, "作業を開始します。"),
        (RunEventType.MESSAGE, "作業が完了しました。"),
        (RunEventType.STATE, None),
        (RunEventType.MESSAGE, "回答を検証します。"),
        (RunEventType.MESSAGE, "参照元PDFを検証しています。"),
        (RunEventType.MESSAGE, "回答を検証しました。"),
        (RunEventType.ANSWER, None),
    ]


def test_execute_chat_run_rejects_invalid_timeout_seconds() -> None:
    """観点：実行全体timeout設定。

    確認：0秒以下の設定では実行UseCaseを生成できない。
    """
    repository = InMemoryChatRepository()

    try:
        ExecuteChatRunUseCase(
            repository=repository,
            codex_runner=FakeCodexRunner(results=()),
            answer_validator=ParsingAnswerValidator(),
            event_publisher=RecordingPublisher(),
            timeout_seconds=0,
        )
    except ValueError as exc:
        assert "timeout_seconds" in str(exc)
    else:
        raise AssertionError("不正timeoutが拒否されませんでした。")


def test_execute_chat_run_completes_cancel_when_run_is_already_canceling() -> None:
    """観点：開始前キャンセル。

    確認：実行開始時にキャンセル要求中のrunはCodexを起動せずキャンセル済みにする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    repository.set_run_state(
        accepted.chat_id, accepted.run_id, RunState.CANCEL_REQUESTED
    )
    runner = FakeCodexRunner(results=())
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-505")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.CANCELED
    assert runner.prompts == []
    assert publisher.events[-1].event is RunEventType.CANCELED


def test_execute_chat_run_marks_error_when_start_state_update_is_stale() -> None:
    """観点：実行開始時の状態競合。

    確認：受付から実行中への条件付き更新が不成立の場合はCodexを起動せずエラー終端する。
    """
    repository = StaleStartRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    runner = FakeCodexRunner(results=())
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-514")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert runner.prompts == []
    assert publisher.events[-1].event is RunEventType.ERROR


def test_execute_chat_run_marks_error_when_generated_answer_is_invalid() -> None:
    """観点：チャット実行処理の異常系。

    確認：固定検証に失敗した回答候補を保存せず、runをエラー終端する。
    """
    repository = InMemoryChatRepository(
        now_values=(
            datetime(2026, 5, 9, 10, 0, tzinfo=UTC),
            datetime(2026, 5, 9, 10, 1, tzinfo=UTC),
        )
    )
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json='{"payload":{"kind":"final","answers":[]}}',
                ),
            )
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id)

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == "回答を検証できませんでした。"
    assert [message.text for message in detail.runs[0].intermediate_messages] == [
        "作業を開始します。",
        "作業が完了しました。",
        "回答を検証します。",
    ]
    assert publisher.events[-1].event is RunEventType.ERROR


def test_execute_chat_run_regenerates_when_validator_requests_retry() -> None:
    """観点：チャット実行処理。確認：検証結果が再生成指示の場合、生成へ戻る。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    runner = FakeCodexRunner(
        results=(
            CodexRunResult(
                conversation_id="codex-thread-1",
                intermediate_messages=(),
                final_answer_json='{"payload":{"kind":"final","answers":[]}}',
            ),
            CodexRunResult(
                conversation_id="codex-thread-1",
                intermediate_messages=(),
                final_answer_json=(
                    '{"payload":{"kind":"final","answers":[{"text":"修正後回答",'
                    '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                    '"start_page":1,"end_page":1}}]}]}}'
                ),
            ),
        )
    )
    validator = QueuedAnswerValidator(
        results=(
            AnswerValidationResult(
                status=ValidationStatus.REGENERATE,
                regeneration_instruction="参照元を具体化してください。",
            ),
            AnswerValidationResult(
                status=ValidationStatus.ACCEPTED,
                candidate=_answer_candidate("修正後回答"),
            ),
        )
    )
    publisher = RecordingPublisher()
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=validator,
        event_publisher=publisher,
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id)

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.COMPLETED
    assert detail.runs[0].answer is not None
    assert detail.runs[0].answer.blocks[0].markdown == "修正後回答"
    assert [message.text for message in detail.runs[0].intermediate_messages] == [
        "作業を開始します。",
        "作業が完了しました。",
        "回答を検証します。",
        "回答を修正します。",
        "作業が完了しました。",
        "回答を検証します。",
        "回答を検証しました。",
    ]
    assert [message.text for message in detail.runs[0].intermediate_messages].count(
        "作業を開始します。"
    ) == 1
    assert runner.prompts[1] == "資料を要約してください\n\n参照元を具体化してください。"
    assert validator.retry_counts == [0, 1]
    assert validator.user_instructions == [
        "資料を要約してください",
        "資料を要約してください",
    ]
    assert trace_logger.records == []


def test_execute_chat_run_writes_trace_when_validation_reaches_retry_limit() -> None:
    """観点：チャット実行処理の異常系。確認：検証不合格が上限到達した場合だけ記録する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    runner = FakeCodexRunner(
        results=(
            CodexRunResult(
                conversation_id="codex-thread-1",
                intermediate_messages=(),
                final_answer_json='{"payload":{"kind":"final","answers":[]}}',
            ),
            CodexRunResult(
                conversation_id="codex-thread-1",
                intermediate_messages=(),
                final_answer_json='{"payload":{"kind":"final","answers":[]}}',
            ),
        )
    )
    validator = QueuedAnswerValidator(
        results=(
            AnswerValidationResult(
                status=ValidationStatus.REGENERATE,
                regeneration_instruction="1回目の検証不合格",
            ),
            AnswerValidationResult(
                status=ValidationStatus.FAILED,
                regeneration_instruction="最後の検証不合格",
                user_message="回答の生成に失敗しました。再度お試しください。",
            ),
        )
    )
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=validator,
        event_publisher=RecordingPublisher(),
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-validation")

    assert [record.event_name for record in trace_logger.records] == [
        "validation_retry_limit_reached"
    ]
    assert trace_logger.records[0].stage == "validation"
    assert trace_logger.records[0].retry_count == 1
    assert trace_logger.records[0].validation_failure_reason == "最後の検証不合格"
    assert trace_logger.records[0].message == "最後の検証不合格"


def test_execute_chat_run_publishes_revision_message_before_retry_generation() -> None:
    """観点：再生成前の固定中間メッセージ。

    確認：検証不合格後、次の生成用Codex起動前に修正開始メッセージを保存する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    runner = RetryMessageObservingCodexRunner(repository=repository)
    validator = QueuedAnswerValidator(
        results=(
            AnswerValidationResult(
                status=ValidationStatus.REGENERATE,
                regeneration_instruction="参照元を具体化してください。",
            ),
            AnswerValidationResult(
                status=ValidationStatus.ACCEPTED,
                candidate=_answer_candidate("修正後回答"),
            ),
        )
    )
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=validator,
        event_publisher=RecordingPublisher(),
    )

    use_case.execute(accepted.chat_id, accepted.run_id)

    assert runner.revision_message_was_persisted_before_retry_generation


def test_execute_chat_run_saves_adopted_artifacts() -> None:
    """観点：チャット実行処理。確認：検証済み回答の成果物URLとメタ情報を保存する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("図を作ってください")
    artifact_id = UUID("00000000-0000-0000-0000-000000000801")
    artifact_saver = RecordingArtifactSaver(
        saved=SavedAnswerBlocksArtifacts(
            blocks=(
                SavedAnswerBlockArtifacts(
                    markdown=f"![図](/api/artifacts/{artifact_id})",
                    artifacts=(
                        ArtifactReference(
                            artifact_id=artifact_id,
                            mime_type="image/png",
                            relative_path=f"{accepted.run_id}/{artifact_id}.png",
                        ),
                    ),
                ),
            )
        )
    )
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json=(
                        '{"payload":{"kind":"final","answers":[{"text":"![図](artifacts/chart.png)",'
                        '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                        '"start_page":1,"end_page":1}}]}]}}'
                    ),
                ),
            )
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=RecordingPublisher(),
        artifact_saver=artifact_saver,
        session_workdir=Path("/codex/sessions/user/session"),
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-501")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].answer is not None
    assert (
        detail.runs[0].answer.blocks[0].markdown
        == f"![図](/api/artifacts/{artifact_id})"
    )
    assert detail.runs[0].answer.blocks[0].artifacts[0].artifact_id == artifact_id
    assert artifact_saver.calls == [
        (
            ("![図](artifacts/chart.png)",),
            accepted.run_id,
            Path("/codex/sessions/user/session"),
            "trace-501",
        )
    ]


def test_execute_chat_run_marks_error_when_artifact_workdir_is_missing() -> None:
    """観点：成果物保存の事前条件。

    確認：採用済み成果物保存が必要なのに作業領域を解決できない場合はエラーにする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("図を作ってください")
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json=(
                        '{"payload":{"kind":"final","answers":[{"text":"![図](artifacts/chart.png)",'
                        '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                        '"start_page":1,"end_page":1}}]}]}}'
                    ),
                ),
            )
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=RecordingPublisher(),
        artifact_saver=RecordingArtifactSaver(
            saved=SavedAnswerBlocksArtifacts(
                blocks=(SavedAnswerBlockArtifacts(markdown="未使用", artifacts=()),)
            )
        ),
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-506")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == "回答を検証できませんでした。"


def test_execute_chat_run_marks_error_when_validator_returns_no_candidate() -> None:
    """観点：検証結果不整合。

    確認：採用可能なのに回答候補がない場合は回答を保存せずエラーにする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json='{"payload":{"kind":"final","answers":[]}}',
                ),
            )
        ),
        answer_validator=AdoptionWithoutCandidateValidator(),
        event_publisher=RecordingPublisher(),
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-507")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == "回答を検証できませんでした。"


def test_execute_chat_run_saves_deadline_and_passes_remaining_seconds() -> None:
    """観点：全体deadline。

    確認：実行中遷移でdeadlineを保存し、生成・検証へdeadlineから算出した残り秒数を渡す。
    """
    started_at = datetime(2026, 5, 9, 10, 0, tzinfo=UTC)
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    runner = FakeCodexRunner(
        results=(
            CodexRunResult(
                conversation_id="codex-thread-1",
                intermediate_messages=(),
                final_answer_json=(
                    '{"payload":{"kind":"final","answers":[{"text":"回答",'
                    '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                    '"start_page":1,"end_page":1}}]}]}}'
                ),
            ),
        )
    )
    validator = ParsingAnswerValidator()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=validator,
        event_publisher=RecordingPublisher(),
        timeout_seconds=300,
        clock=SequenceClock(
            (
                started_at,
                started_at,
                started_at + timedelta(seconds=5),
            )
        ),
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-510")

    assert repository.run_execution_deadline_for_test(
        accepted.chat_id, accepted.run_id
    ) == started_at + timedelta(seconds=300)
    assert runner.timeout_seconds == [300]
    assert validator.timeout_seconds == [295]


def test_execute_chat_run_does_not_keep_transaction_open_during_codex_generation() -> (
    None
):
    """観点：チャット実行処理のトランザクション境界。

    確認：生成用Codex実行中にDBトランザクションを開きっぱなしにしない。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    transaction_manager = RecordingTransactionManager()
    runner = TransactionObservingCodexRunner(transaction_manager)
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=ParsingAnswerValidator(),
        event_publisher=RecordingPublisher(),
        transaction_manager=transaction_manager,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-transaction")

    assert runner.transaction_was_active_during_generation is False
    assert transaction_manager.entered_count > 0


def test_execute_chat_run_times_out_before_next_codex_exec_when_deadline_exceeded() -> (
    None
):
    """観点：全体deadline。

    確認：生成後にdeadlineを超過していれば検証用Codexを起動せずタイムアウト終端する。
    """
    started_at = datetime(2026, 5, 9, 10, 0, tzinfo=UTC)
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    runner = FakeCodexRunner(
        results=(
            CodexRunResult(
                conversation_id="codex-thread-1",
                intermediate_messages=(),
                final_answer_json=(
                    '{"payload":{"kind":"final","answers":[{"text":"回答",'
                    '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                    '"start_page":1,"end_page":1}}]}]}}'
                ),
            ),
        )
    )
    validator = ParsingAnswerValidator()
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=runner,
        answer_validator=validator,
        event_publisher=publisher,
        timeout_seconds=300,
        clock=SequenceClock(
            (
                started_at,
                started_at,
                started_at + timedelta(seconds=301),
            )
        ),
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-511")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.TIMED_OUT
    assert detail.runs[0].answer is None
    assert validator.timeout_seconds == []
    assert publisher.events[-1].event is RunEventType.ERROR
    assert publisher.events[-1].state is RunState.TIMED_OUT


def test_execute_chat_run_marks_error_when_codex_generation_fails() -> None:
    """観点：チャット実行処理の異常系。確認：Codex失敗時はエラー終端する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FailingCodexRunner(
            error=AppError(
                ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="Codex実行が失敗しました。",
            )
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-502")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == (
        "回答の生成に失敗しました。再度お試しください。"
    )
    assert publisher.events[-1].event is RunEventType.ERROR
    assert publisher.events[-1].user_message == (
        "回答の生成に失敗しました。再度お試しください。"
    )
    assert trace_logger.records[-1].event_name == "execution_failed"
    assert trace_logger.records[-1].stage == "generation"
    assert trace_logger.records[-1].trace_id == "trace-502"
    assert trace_logger.records[-1].chat_id == accepted.chat_id
    assert trace_logger.records[-1].run_id == accepted.run_id
    assert trace_logger.records[-1].error_type == "system"


def test_execute_chat_run_marks_validation_error_for_invalid_validator_result() -> None:
    """観点：チャット実行処理の異常系。

    確認：検証用Codexの最終出力形式不正は生成失敗ではなく検証失敗として終端する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json=_valid_answer_json(),
                ),
            )
        ),
        answer_validator=FailingValidationValidator(
            error=ValidationResultFormatError("検証結果の形式が不正です。")
        ),
        event_publisher=publisher,
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-516")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == (
        "回答の検証に失敗しました。再度お試しください。"
    )
    assert publisher.events[-1].event is RunEventType.ERROR
    assert publisher.events[-1].user_message == (
        "回答の検証に失敗しました。再度お試しください。"
    )
    assert trace_logger.records[-1].event_name == "execution_failed"
    assert trace_logger.records[-1].stage == "validation"
    assert trace_logger.records[-1].trace_id == "trace-516"
    assert trace_logger.records[-1].error_type == "system"
    assert trace_logger.records[-1].validation_failure_reason == (
        "検証結果の形式が不正です。"
    )


def test_execute_chat_run_marks_error_when_reference_pdf_read_fails() -> None:
    """観点：チャット実行処理の異常系。

    確認：検証フェーズで参照元PDFを読み取れない場合は再生成せず、PDF読み取りエラーとして終端する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json=_valid_answer_json(),
                ),
            )
        ),
        answer_validator=FailingValidationValidator(
            error=ReferencePdfReadError(
                relative_path="raw/pdf/manual.pdf",
                cause=RuntimeError("AES algorithm is unavailable"),
            )
        ),
        event_publisher=publisher,
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-515")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == "PDF読み取り中にエラーが発生しました。"
    assert publisher.events[-1].event is RunEventType.ERROR
    assert publisher.events[-1].user_message == (
        "PDF読み取り中にエラーが発生しました。"
    )
    assert trace_logger.records[-1].event_name == "execution_failed"
    assert trace_logger.records[-1].stage == "validation"
    assert trace_logger.records[-1].trace_id == "trace-515"
    assert trace_logger.records[-1].error_type == "system"
    assert trace_logger.records[-1].validation_failure_reason == (
        "参照元PDFを読み取れません: raw/pdf/manual.pdf "
        "(RuntimeError: AES algorithm is unavailable)"
    )


def test_execute_chat_run_marks_error_when_unexpected_adoption_failure_occurs() -> None:
    """観点：チャット実行処理の異常系。

    確認：検証完了後の回答採用で予期しない例外が出ても、runをエラー終端してトレースログを残す。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json=_valid_answer_json(),
                ),
            )
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
        artifact_saver=FailingArtifactSaver(
            error=RuntimeError("採用済み回答の保存前処理に失敗しました。")
        ),
        session_workdir=Path("/tmp/session"),
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-516")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.ERROR
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == (
        "予期しないエラーが発生しました。開発者にお問い合わせください。"
    )
    assert [message.text for message in detail.runs[0].intermediate_messages][-2:] == [
        "回答を検証します。",
        "回答を検証しました。",
    ]
    assert publisher.events[-1].event is RunEventType.ERROR
    assert publisher.events[-1].user_message == (
        "予期しないエラーが発生しました。開発者にお問い合わせください。"
    )
    assert trace_logger.records[-1].event_name == "execution_failed"
    assert trace_logger.records[-1].stage == "execution"
    assert trace_logger.records[-1].trace_id == "trace-516"
    assert trace_logger.records[-1].error_type == "system"
    assert trace_logger.records[-1].exception_type == "RuntimeError"
    assert trace_logger.records[-1].message == (
        "採用済み回答の保存前処理に失敗しました。"
    )


def test_execute_chat_run_treats_app_error_after_cancel_as_canceled() -> None:
    """観点：生成失敗とキャンセルの競合。

    確認：Codex失敗前にキャンセル要求中になっている場合はエラーではなくキャンセル済みにする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=CancelingFailingCodexRunner(
            repository=repository,
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-509")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.CANCELED
    assert detail.runs[0].answer is None
    assert publisher.events[-1].event is RunEventType.CANCELED
    assert trace_logger.records == []


def test_execute_chat_run_marks_timeout_when_codex_times_out() -> None:
    """観点：チャット実行処理の異常系。確認：Codexタイムアウト時はタイムアウト終端する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    trace_logger = RecordingTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FailingCodexRunner(error=RunTimeoutError()),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
        trace_logger=trace_logger,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-503")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.TIMED_OUT
    assert detail.runs[0].answer is None
    assert detail.runs[0].user_message == (
        "回答生成が時間内に完了しませんでした。ユーザ指示を絞って再度お試しください。"
    )
    assert publisher.events[-1].event is RunEventType.ERROR
    assert publisher.events[-1].state is RunState.TIMED_OUT
    assert trace_logger.records[-1].event_name == "execution_timeout"
    assert trace_logger.records[-1].exception_type == "RunTimeoutError"
    assert trace_logger.records[-1].run_state == "タイムアウト"


def test_execute_chat_run_keeps_cancel_when_timeout_races_with_cancel() -> None:
    """観点：キャンセルとタイムアウトの競合。

    確認：Codexタイムアウト前にキャンセル要求中になっていた場合はキャンセル済みを優先する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=CancelingTimeoutCodexRunner(
            repository=repository,
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-508")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.CANCELED
    assert detail.runs[0].user_message == "処理をキャンセルしました。"
    assert publisher.events[-1].event is RunEventType.CANCELED


def test_execute_chat_run_does_not_adopt_answer_after_cancel() -> None:
    """観点：キャンセル競合。確認：キャンセル済みrunへ回答や途中成果を採用しない。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=CancelingCodexRunner(
            repository=repository,
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
        ),
        answer_validator=ParsingAnswerValidator(),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-504")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.CANCELED
    assert detail.runs[0].answer is None
    assert [message.text for message in detail.runs[0].intermediate_messages] == [
        "作業を開始します。"
    ]
    assert publisher.events[-1].event is RunEventType.CANCELED


def test_execute_chat_run_does_not_adopt_when_validation_side_cancels() -> None:
    """観点：検証後キャンセル競合。

    確認：検証境界の処理中にキャンセル要求中になった場合は回答を採用しない。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json='{"payload":{"kind":"final","answers":[]}}',
                ),
            )
        ),
        answer_validator=CancelingValidationValidator(
            repository=repository,
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
            result=AnswerValidationResult(
                status=ValidationStatus.ACCEPTED,
                candidate=_answer_candidate("採用してはいけない回答"),
            ),
        ),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-512")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.CANCELED
    assert detail.runs[0].answer is None
    assert publisher.events[-1].event is RunEventType.CANCELED


def test_execute_chat_run_keeps_cancel_when_validation_failure_races_with_cancel() -> (
    None
):
    """観点：検証失敗とキャンセルの競合。

    確認：検証失敗処理の直前にキャンセル要求中ならエラーへ上書きしない。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約してください")
    publisher = RecordingPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        codex_runner=FakeCodexRunner(
            results=(
                CodexRunResult(
                    conversation_id="codex-thread-1",
                    intermediate_messages=(),
                    final_answer_json='{"payload":{"kind":"final","answers":[]}}',
                ),
            )
        ),
        answer_validator=CancelingValidationValidator(
            repository=repository,
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
            result=AnswerValidationResult(
                status=ValidationStatus.FAILED,
                user_message="採用してはいけないエラー",
            ),
        ),
        event_publisher=publisher,
    )

    use_case.execute(accepted.chat_id, accepted.run_id, trace_id="trace-513")

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.CANCELED
    assert detail.runs[0].user_message == "処理をキャンセルしました。"
    assert publisher.events[-1].event is RunEventType.CANCELED


@dataclass(slots=True)
class FakeCodexRunner:
    """テスト用CodexRunner。"""

    results: tuple[CodexRunResult, ...]
    prompts: list[str] = field(default_factory=list)
    timeout_seconds: list[int] = field(default_factory=list)

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """固定の生成結果を返す。"""
        _ = (chat_id, run_id, trace_id, on_intermediate_message)
        self.prompts.append(user_instruction)
        self.timeout_seconds.append(timeout_seconds)
        return self.results[len(self.prompts) - 1]


@dataclass(slots=True)
class TransactionObservingCodexRunner:
    """生成実行中のトランザクション状態を記録するテスト用CodexRunner。"""

    transaction_manager: "RecordingTransactionManager"
    transaction_was_active_during_generation: bool | None = None

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """TransactionManagerが非アクティブな状態で固定結果を返す。"""
        _ = (
            chat_id,
            run_id,
            user_instruction,
            timeout_seconds,
            trace_id,
            on_intermediate_message,
        )
        self.transaction_was_active_during_generation = self.transaction_manager.active
        return CodexRunResult(
            conversation_id="codex-thread-1",
            intermediate_messages=(),
            final_answer_json=_valid_answer_json(),
        )


@dataclass(slots=True)
class StreamingFakeCodexRunner:
    """生成中の中間メッセージ通知を検証するテスト用CodexRunner。"""

    repository: InMemoryChatRepository
    publisher: "RecordingPublisher"
    start_message_was_persisted_before_generation: bool = False
    message_was_persisted_before_return: bool = False
    message_was_published_before_return: bool = False

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """生成完了前に中間メッセージを通知する。"""
        _ = (user_instruction, timeout_seconds, trace_id)
        if on_intermediate_message is None:
            raise AssertionError("中間メッセージ通知コールバックが渡されていません。")
        detail = self.repository.get_chat_detail(chat_id)
        self.start_message_was_persisted_before_generation = (
            detail.runs[0].intermediate_messages[-1].text == "作業を開始します。"
        )
        on_intermediate_message("資料を確認しています。")
        detail = self.repository.get_chat_detail(chat_id)
        self.message_was_persisted_before_return = (
            detail.runs[0].intermediate_messages[-1].text == "資料を確認しています。"
        )
        self.message_was_published_before_return = (
            self.publisher.events[-1].event is RunEventType.MESSAGE
            and self.publisher.events[-1].text == "資料を確認しています。"
        )
        return CodexRunResult(
            conversation_id="codex-thread-1",
            intermediate_messages=(),
            final_answer_json=(
                '{"payload":{"kind":"final","answers":[{"text":"回答","references":[]}]}}'
            ),
        )


@dataclass(slots=True)
class RetryMessageObservingCodexRunner:
    """再生成直前の固定中間メッセージを検証するテスト用CodexRunner。"""

    repository: InMemoryChatRepository
    prompts: list[str] = field(default_factory=list)
    revision_message_was_persisted_before_retry_generation: bool = False

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """呼び出し順に固定の生成結果を返す。"""
        _ = (run_id, timeout_seconds, trace_id, on_intermediate_message)
        self.prompts.append(user_instruction)
        if len(self.prompts) == 2:
            detail = self.repository.get_chat_detail(chat_id)
            self.revision_message_was_persisted_before_retry_generation = (
                detail.runs[0].intermediate_messages[-1].text == "回答を修正します。"
            )
            return CodexRunResult(
                conversation_id="codex-thread-1",
                intermediate_messages=(),
                final_answer_json=(
                    '{"payload":{"kind":"final","answers":[{"text":"修正後回答",'
                    '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                    '"start_page":1,"end_page":1}}]}]}}'
                ),
            )
        return CodexRunResult(
            conversation_id="codex-thread-1",
            intermediate_messages=(),
            final_answer_json='{"payload":{"kind":"final","answers":[]}}',
        )


@dataclass(slots=True)
class FailingCodexRunner:
    """例外を返すテスト用CodexRunner。"""

    error: AppError | RunTimeoutError

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """固定例外を送出する。"""
        _ = (
            chat_id,
            run_id,
            user_instruction,
            timeout_seconds,
            trace_id,
            on_intermediate_message,
        )
        raise self.error


@dataclass(slots=True)
class CancelingCodexRunner:
    """生成中にキャンセル済みへするテスト用CodexRunner。"""

    repository: InMemoryChatRepository
    chat_id: UUID
    run_id: UUID

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """キャンセル済みへ更新してから生成結果を返す。"""
        _ = (
            chat_id,
            run_id,
            user_instruction,
            timeout_seconds,
            trace_id,
            on_intermediate_message,
        )
        self.repository.cancel_run(self.chat_id, self.run_id)
        return CodexRunResult(
            conversation_id="codex-thread-1",
            intermediate_messages=("採用してはいけない中間メッセージ",),
            final_answer_json=(
                '{"payload":{"kind":"final","answers":[{"text":"採用してはいけない回答",'
                '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
                '"start_page":1,"end_page":1}}]}]}}'
            ),
        )


@dataclass(slots=True)
class CancelingFailingCodexRunner:
    """生成中にキャンセル要求中へした後、AppErrorを返すテスト用CodexRunner。"""

    repository: InMemoryChatRepository
    chat_id: UUID
    run_id: UUID

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """キャンセル要求中へ更新してからAppErrorを送出する。"""
        _ = (
            chat_id,
            run_id,
            user_instruction,
            timeout_seconds,
            trace_id,
            on_intermediate_message,
        )
        self.repository.update_run_state_if_current(
            chat_id=self.chat_id,
            run_id=self.run_id,
            expected_states=(RunState.RUNNING,),
            state=RunState.CANCEL_REQUESTED,
            user_message="処理をキャンセルしています。",
        )
        raise AppError(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="Codex実行が失敗しました。",
        )


class StaleStartRepository(InMemoryChatRepository):
    """最初の状態条件付き更新だけ不成立にするRepository。"""

    def __init__(self) -> None:
        super().__init__()
        self.update_calls = 0

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
        execution_deadline_at: datetime | None = None,
    ) -> bool:
        """初回だけ状態競合にする。"""
        self.update_calls += 1
        if self.update_calls == 1:
            return False
        return super().update_run_state_if_current(
            chat_id=chat_id,
            run_id=run_id,
            expected_states=expected_states,
            state=state,
            user_message=user_message,
            execution_deadline_at=execution_deadline_at,
        )


@dataclass(slots=True)
class CancelingTimeoutCodexRunner:
    """生成中にキャンセル要求中へした後、タイムアウトを返すテスト用CodexRunner。"""

    repository: InMemoryChatRepository
    chat_id: UUID
    run_id: UUID

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """キャンセル要求中へ更新してからタイムアウトを送出する。"""
        _ = (
            chat_id,
            run_id,
            user_instruction,
            timeout_seconds,
            trace_id,
            on_intermediate_message,
        )
        self.repository.update_run_state_if_current(
            chat_id=self.chat_id,
            run_id=self.run_id,
            expected_states=(RunState.RUNNING,),
            state=RunState.CANCEL_REQUESTED,
            user_message="処理をキャンセルしています。",
        )
        raise RunTimeoutError()


@dataclass(slots=True)
class AdoptionWithoutCandidateValidator:
    """採用可能だが候補なしを返す不整合Validator。"""

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        timeout_seconds: int,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        """採用可能ステータスだけを返す。"""
        _ = (
            raw_answer_json,
            retry_count,
            user_instruction,
            chat_id,
            run_id,
            trace_id,
            timeout_seconds,
            on_intermediate_message,
            session_workdir,
        )
        return AnswerValidationResult(status=ValidationStatus.ACCEPTED)


@dataclass(slots=True)
class CancelingValidationValidator:
    """検証中にキャンセル要求中へするテスト用Validator。"""

    repository: InMemoryChatRepository
    chat_id: UUID
    run_id: UUID
    result: AnswerValidationResult

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        timeout_seconds: int,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        """キャンセル要求中へ更新してから固定結果を返す。"""
        _ = (
            raw_answer_json,
            retry_count,
            user_instruction,
            chat_id,
            run_id,
            trace_id,
            timeout_seconds,
            on_intermediate_message,
            session_workdir,
        )
        self.repository.update_run_state_if_current(
            chat_id=self.chat_id,
            run_id=self.run_id,
            expected_states=(RunState.VALIDATING,),
            state=RunState.CANCEL_REQUESTED,
            user_message="処理をキャンセルしています。",
        )
        return self.result


@dataclass(slots=True)
class ParsingAnswerValidator:
    """生成JSONを固定検証だけで採用判定するテスト用Validator。"""

    timeout_seconds: list[int] = field(default_factory=list)

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        timeout_seconds: int,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        _ = (
            retry_count,
            user_instruction,
            chat_id,
            run_id,
            trace_id,
            on_intermediate_message,
            session_workdir,
        )
        self.timeout_seconds.append(timeout_seconds)
        try:
            candidate = parse_generation_final_output(raw_answer_json)
        except AnswerParseError:
            return AnswerValidationResult(
                status=ValidationStatus.FAILED,
                user_message="回答を検証できませんでした。",
            )
        return AnswerValidationResult(
            status=ValidationStatus.ACCEPTED, candidate=candidate
        )


@dataclass(slots=True)
class QueuedAnswerValidator:
    """呼び出し順に検証結果を返すテスト用Validator。"""

    results: tuple[AnswerValidationResult, ...]
    retry_counts: list[int] = field(default_factory=list)
    user_instructions: list[str] = field(default_factory=list)

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        timeout_seconds: int,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        _ = (
            raw_answer_json,
            chat_id,
            run_id,
            trace_id,
            timeout_seconds,
            on_intermediate_message,
            session_workdir,
        )
        self.retry_counts.append(retry_count)
        self.user_instructions.append(user_instruction)
        return self.results[len(self.retry_counts) - 1]


@dataclass(slots=True)
class FailingValidationValidator:
    """固定例外を返すテスト用Validator。"""

    error: AppError

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        timeout_seconds: int,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        """固定例外を送出する。"""
        _ = (
            raw_answer_json,
            retry_count,
            user_instruction,
            chat_id,
            run_id,
            trace_id,
            timeout_seconds,
            on_intermediate_message,
            session_workdir,
        )
        raise self.error


@dataclass(slots=True)
class ValidationStreamingAnswerValidator:
    """検証中の中間メッセージ通知を検証するテスト用Validator。"""

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        timeout_seconds: int,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        """検証完了前に中間メッセージを通知する。"""
        _ = (
            retry_count,
            user_instruction,
            chat_id,
            run_id,
            trace_id,
            timeout_seconds,
            session_workdir,
        )
        if on_intermediate_message is None:
            raise AssertionError("検証中間メッセージ通知コールバックがありません。")
        on_intermediate_message("参照元PDFを検証しています。")
        return AnswerValidationResult(
            status=ValidationStatus.ACCEPTED,
            candidate=parse_generation_final_output(raw_answer_json),
        )


@dataclass(slots=True)
class RecordingArtifactSaver:
    """成果物保存呼び出しを記録するテスト用Saver。"""

    saved: SavedAnswerBlocksArtifacts
    calls: list[tuple[tuple[str, ...], UUID, Path, str]] = field(default_factory=list)

    def save_for_answer_blocks(
        self,
        markdowns: tuple[str, ...],
        run_id: UUID,
        session_workdir: Path,
        trace_id: str,
    ) -> SavedAnswerBlocksArtifacts:
        self.calls.append((markdowns, run_id, session_workdir, trace_id))
        return self.saved


@dataclass(slots=True)
class FailingArtifactSaver:
    """例外を送出するテスト用Saver。"""

    error: Exception

    def save_for_answer_blocks(
        self,
        markdowns: tuple[str, ...],
        run_id: UUID,
        session_workdir: Path,
        trace_id: str,
    ) -> SavedAnswerBlocksArtifacts:
        _ = (markdowns, run_id, session_workdir, trace_id)
        raise self.error


@dataclass(slots=True)
class RecordingPublisher:
    """テスト用イベント発行先。"""

    events: list[RunEvent] = field(default_factory=list)

    def publish(self, event: RunEvent) -> None:
        """発行イベントを記録する。"""
        self.events.append(event)


@dataclass(slots=True)
class RecordingTraceLogger:
    """テスト用トレースログ出力先。"""

    records: list[TraceLogRecord] = field(default_factory=list)

    def write(self, record: TraceLogRecord) -> None:
        """出力レコードを記録する。"""
        self.records.append(record)


@dataclass(slots=True)
class SequenceClock:
    """テスト用に現在時刻を順番に返す時計。"""

    values: tuple[datetime, ...]
    index: int = 0

    def now(self) -> datetime:
        """登録済み時刻を順番に返す。"""
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value

    def now_utc(self) -> datetime:
        """登録済み時刻をUTC現在時刻として順番に返す。"""
        return self.now()

    def now_app_timezone(self) -> datetime:
        """登録済み時刻をアプリタイムゾーン現在時刻として順番に返す。"""
        return self.now()


@dataclass(slots=True)
class SequenceIdGenerator:
    """テスト用にUUIDを順番に返すID発番器。"""

    next_int: int = 1

    def new_uuid(self) -> UUID:
        """連番からUUIDを生成する。"""
        generated = UUID(int=self.next_int)
        self.next_int += 1
        return generated


@dataclass(slots=True)
class RecordingTransactionManager:
    """テスト用TransactionManager。"""

    entered_count: int = 0
    active: bool = False

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """トランザクション状態を記録する。"""
        self.entered_count += 1
        if self.active:
            raise AssertionError("トランザクションがネストされました。")
        self.active = True
        try:
            yield
        finally:
            self.active = False


def _valid_answer_json() -> str:
    return (
        '{"payload":{"kind":"final","answers":[{"text":"要点はAです。",'
        '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
        '"start_page":2,"end_page":3}}]}]}}'
    )


def _answer_candidate(text: str) -> ParsedAnswerCandidate:
    return ParsedAnswerCandidate(
        blocks=(
            ParsedAnswerBlock(
                markdown=text,
                references=(
                    _pdf_reference(
                        label="manual.pdf",
                        relative_path="manual.pdf",
                        page_start=1,
                        page_end=1,
                    ),
                ),
            ),
        ),
    )


def _pdf_reference(
    *,
    label: str,
    relative_path: str,
    page_start: int,
    page_end: int,
) -> PdfReference:
    return PdfReference(
        label=label,
        locator=PdfLocator(
            relative_path=relative_path,
            page_start=page_start,
            page_end=page_end,
        ),
    )

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.ports.codex.dto import (
    CodexGenerationRequest,
    CodexGenerationResult,
)
from backend.application.validation.validate_answer import (
    ValidateAnswerCommand,
    ValidationStatus,
)
from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    F003_USER_ID,
    RUN_ID_VALUE,
    FakeTransactionManager,
    FixedClock,
)
from backend.tests.support.codex import (
    FakeChatExecutionRepository,
    FakeCodexGenerationRunner,
    FakeRunEventPublisher,
    FakeTraceLogger,
    generation_result,
    valid_candidate_json,
)


class ValidationCommandLike(Protocol):
    """実行ユースケースから回答検証へ渡す要求の観測項目。"""

    @property
    def candidate_json(self) -> str: ...

    @property
    def retry_count(self) -> int: ...

    @property
    def remaining_seconds(self) -> int: ...


class SaveArtifactsCommandLike(Protocol):
    """実行ユースケースから採用済み成果物保存へ渡す要求の観測項目。"""

    @property
    def markdown_blocks(self) -> tuple[str, ...]: ...

    @property
    def user_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class ValidatedReference:
    source_type: str
    path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ValidatedBlock:
    markdown: str
    references: tuple[ValidatedReference, ...]
    artifact_links: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    blocks: tuple[ValidatedBlock, ...]


@dataclass(frozen=True, slots=True)
class ValidationResultRecord:
    status: str
    answer: ValidatedAnswer | None = None
    regeneration_instruction: str | None = None
    diagnostic_message: str | None = None
    validation_conversation_id: str | None = "val-thread-001"


@dataclass(slots=True)
class FakeAnswerValidator:
    results: list[ValidationResultRecord]
    requests: list[ValidateAnswerCommand] = field(default_factory=list)

    def execute(self, command: ValidateAnswerCommand) -> ValidationResultRecord:
        self.requests.append(command)
        if not self.results:
            raise RuntimeError("回答検証Fake結果が不足しています。")
        return self.results.pop(0)


@dataclass(frozen=True, slots=True)
class SavedArtifactBlock:
    markdown: str
    artifacts: tuple[SavedArtifactMetadataRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class SavedArtifactMetadataRecord:
    artifact_id: str | UUID
    storage_path: str
    public_url: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class SavedArtifactResult:
    blocks: tuple[SavedArtifactBlock, ...]


@dataclass(slots=True)
class FakeAdoptedArtifactSaver:
    requests: list[SaveArtifactsCommandLike] = field(default_factory=list)

    def execute(self, command: SaveArtifactsCommandLike) -> SavedArtifactResult:
        self.requests.append(command)
        return SavedArtifactResult(
            blocks=tuple(
                SavedArtifactBlock(
                    markdown=markdown.replace("artifacts/", "/api/artifacts/"),
                )
                for markdown in command.markdown_blocks
            ),
        )


@dataclass(slots=True)
class RaisingAnswerValidator:
    diagnostic_message: str
    requests: list[ValidateAnswerCommand] = field(default_factory=list)

    def execute(self, command: ValidateAnswerCommand) -> ValidationResultRecord:
        self.requests.append(command)
        raise AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message=self.diagnostic_message,
        )


@dataclass(slots=True)
class FailingAdoptedArtifactSaver:
    diagnostic_message: str
    requests: list[SaveArtifactsCommandLike] = field(default_factory=list)

    def execute(self, command: SaveArtifactsCommandLike) -> SavedArtifactResult:
        self.requests.append(command)
        raise RuntimeError(self.diagnostic_message)


@dataclass(slots=True)
class UuidAdoptedArtifactSaver:
    requests: list[SaveArtifactsCommandLike] = field(default_factory=list)

    def execute(self, command: SaveArtifactsCommandLike) -> SavedArtifactResult:
        self.requests.append(command)
        return SavedArtifactResult(
            blocks=(
                SavedArtifactBlock(
                    markdown="![図](/api/artifacts/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa)",
                    artifacts=(
                        SavedArtifactMetadataRecord(
                            artifact_id=UUID("aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa"),
                            storage_path="user/session/diagram.svg",
                            public_url="/api/artifacts/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa",
                            mime_type="image/svg+xml",
                        ),
                    ),
                ),
            ),
        )


def test_execute_chat_run_completes_generation_validation_and_adoption(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが生成、回答検証、採用保存を順序どおり連携すること
    確認：running、validating、completedへ遷移し、固定メッセージとCodex progressを
    保存・配信し、
    検証済み回答だけを保存してanswerイベントを発行すること
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository()
    generation_runner = FakeCodexGenerationRunner(results=[generation_result(tmp_path)])
    validator = FakeAnswerValidator(
        results=[
            ValidationResultRecord(
                status="accepted",
                answer=ValidatedAnswer(
                    blocks=(
                        ValidatedBlock(
                            markdown="ポンプは定期点検が必要です。",
                            references=(
                                ValidatedReference(
                                    source_type="pdf",
                                    path="manuals/pump.pdf",
                                    page_start=2,
                                    page_end=3,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ],
    )
    artifact_saver = FakeAdoptedArtifactSaver()
    publisher = FakeRunEventPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=generation_runner,
        answer_validator=validator,
        adopted_artifact_saver=artifact_saver,
        event_publisher=publisher,
        clock=FixedClock(),
        trace_logger=FakeTraceLogger(),
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert [state.state for state in repository.states] == [
        RunState.RUNNING.value,
        RunState.VALIDATING.value,
        RunState.COMPLETED.value,
    ]
    assert [message.text for message in repository.intermediate_messages] == [
        "作業を開始します。",
        "調査しています。",
        "作業が完了しました。",
        "回答の検証を開始します。",
        "回答候補を検証しています。",
        "回答の検証を完了しました。",
    ]
    assert repository.saved_answer_runs == [RUN_ID_VALUE]
    assert repository.saved_answer_markdown == ["ポンプは定期点検が必要です。"]
    assert (
        repository.conversation_ids[-1].generation_conversation_id == "gen-thread-001"
    )
    assert (
        repository.conversation_ids[-1].validation_conversation_id == "val-thread-001"
    )
    assert [event.event_name for event in publisher.events][-1] == "answer"
    assert generation_runner.requests[0].remaining_seconds > 0
    assert validator.requests[0].candidate_json == valid_candidate_json()
    assert artifact_saver.requests[0].user_id == F003_USER_ID


def test_execute_chat_run_regenerates_when_validation_requests_retry(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが検証不合格時に再生成へ戻ること
    確認：回答採用前に回答を修正しますメッセージを保存し、再生成要求には
    検証不合格理由と元の利用者指示を含めること
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository()
    generation_runner = FakeCodexGenerationRunner(
        results=[
            generation_result(
                tmp_path,
                candidate_json=valid_candidate_json("初回回答"),
            ),
            generation_result(
                tmp_path,
                candidate_json=valid_candidate_json("修正回答"),
            ),
        ],
    )
    validator = FakeAnswerValidator(
        results=[
            ValidationResultRecord(
                status="regenerate",
                regeneration_instruction="不合格理由：根拠が不足しています。",
            ),
            ValidationResultRecord(
                status="accepted",
                answer=ValidatedAnswer(
                    blocks=(
                        ValidatedBlock(
                            markdown="修正回答",
                            references=(),
                        ),
                    ),
                ),
            ),
        ],
    )
    publisher = FakeRunEventPublisher()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=generation_runner,
        answer_validator=validator,
        adopted_artifact_saver=FakeAdoptedArtifactSaver(),
        event_publisher=publisher,
        clock=FixedClock(),
        trace_logger=FakeTraceLogger(),
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert len(generation_runner.requests) == 2
    assert [state.state for state in repository.states] == [
        RunState.RUNNING.value,
        RunState.VALIDATING.value,
        RunState.RUNNING.value,
        RunState.VALIDATING.value,
        RunState.COMPLETED.value,
    ]
    assert [
        event.payload_state for event in publisher.events if event.event_name == "state"
    ] == [
        RunState.RUNNING.value,
        RunState.VALIDATING.value,
        RunState.RUNNING.value,
        RunState.VALIDATING.value,
    ]
    assert generation_runner.requests[1].regeneration_instruction is not None
    assert "不合格理由：根拠が不足しています。" in (
        generation_runner.requests[1].regeneration_instruction
    )
    assert validator.requests[1].retry_count == 1
    assert "回答を修正します。" in [
        message.text for message in repository.intermediate_messages
    ]
    assert repository.saved_answer_markdown == ["修正回答"]


def test_execute_chat_run_timeout_before_validation_does_not_adopt_answer(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが全体deadlineを超えた回答候補を採用しないこと
    確認：生成後に検証用残り秒数が0以下ならtimed_outへ終端し、回答検証、
    成果物保存、回答保存を行わず、timeout stageのtraceを残すこと
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository()
    trace_logger = FakeTraceLogger()
    generation_runner = FakeCodexGenerationRunner(results=[generation_result(tmp_path)])
    validator = FakeAnswerValidator(
        results=[
            ValidationResultRecord(
                status="accepted",
                answer=ValidatedAnswer(blocks=()),
            ),
        ],
    )
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=generation_runner,
        answer_validator=validator,
        adopted_artifact_saver=FakeAdoptedArtifactSaver(),
        event_publisher=FakeRunEventPublisher(),
        clock=FixedClock(),
        trace_logger=trace_logger,
        execution_deadline_seconds=0,
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert repository.states[-1].state == RunState.TIMED_OUT.value
    assert repository.states[-1].user_message == "処理がタイムアウトしました。"
    assert validator.requests == []
    assert repository.saved_answer_runs == []
    assert trace_logger.records[0].stage == "codex.timeout"
    assert "timeout" in trace_logger.records[0].diagnostic_message


def test_execute_chat_run_traces_validation_limit_failure(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが検証上限超過を利用者向けエラーとtraceへ変換すること
    確認：failed検証結果ではrunをerrorへ終端し、回答を保存せず、
    最後の検証失敗理由をanswer.validation stageのtraceへ残すこと
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository()
    trace_logger = FakeTraceLogger()
    validator = FakeAnswerValidator(
        results=[
            ValidationResultRecord(
                status="failed",
                diagnostic_message="根拠ページが不足しています。",
            ),
        ],
    )
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=FakeCodexGenerationRunner(
            results=[generation_result(tmp_path)],
        ),
        answer_validator=validator,
        adopted_artifact_saver=FakeAdoptedArtifactSaver(),
        event_publisher=FakeRunEventPublisher(),
        clock=FixedClock(),
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert repository.states[-1].state == RunState.ERROR.value
    assert repository.states[-1].user_message is not None
    assert "回答の検証" in repository.states[-1].user_message
    assert repository.saved_answer_runs == []
    assert trace_logger.records[0].stage == "answer.validation"
    assert "根拠ページが不足しています。" in trace_logger.records[0].diagnostic_message
    assert "retry" in trace_logger.records[0].diagnostic_message


def test_execute_chat_run_traces_pdf_read_failure_without_regeneration(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが参照元PDF読込失敗を検証段階の障害として扱うこと
    確認：ValidateAnswerUseCase相当のAppErrorでは再生成へ戻らずerrorへ終端し、
    回答非保存、PDF読込用メッセージ、対象PDFを含むtraceを残すこと
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository()
    trace_logger = FakeTraceLogger()
    validator = RaisingAnswerValidator(
        diagnostic_message="PDF読み取り失敗: manuals/pump.pdf",
    )
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=FakeCodexGenerationRunner(
            results=[generation_result(tmp_path)],
        ),
        answer_validator=validator,
        adopted_artifact_saver=FakeAdoptedArtifactSaver(),
        event_publisher=FakeRunEventPublisher(),
        clock=FixedClock(),
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert repository.states[-1].state == RunState.ERROR.value
    assert repository.states[-1].user_message == "PDF読み取り中にエラーが発生しました。"
    assert repository.saved_answer_runs == []
    assert trace_logger.records[0].stage == "answer.validation"
    assert "manuals/pump.pdf" in trace_logger.records[0].diagnostic_message
    assert "PDF読み取り失敗" in trace_logger.records[0].diagnostic_message


def test_execute_chat_run_traces_artifact_adoption_failure(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが検証後の成果物採用失敗を実行段階の障害として扱うこと
    確認：検証済み回答をDB保存せずerrorへ終端し、利用者向け汎用エラーと
    answer.adoption stageのtraceへ例外要約を残すこと
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository()
    trace_logger = FakeTraceLogger()
    validator = FakeAnswerValidator(
        results=[
            ValidationResultRecord(
                status="accepted",
                answer=ValidatedAnswer(
                    blocks=(
                        ValidatedBlock(
                            markdown="![図](artifacts/diagram.svg)",
                            references=(),
                            artifact_links=("artifacts/diagram.svg",),
                        ),
                    ),
                ),
            ),
        ],
    )
    artifact_saver = FailingAdoptedArtifactSaver(
        diagnostic_message="保存済み成果物領域へコピーできません。",
    )
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=FakeCodexGenerationRunner(
            results=[generation_result(tmp_path)],
        ),
        answer_validator=validator,
        adopted_artifact_saver=artifact_saver,
        event_publisher=FakeRunEventPublisher(),
        clock=FixedClock(),
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert repository.states[-1].state == RunState.ERROR.value
    assert repository.states[-1].user_message == (
        "予期しないエラーが発生しました。開発者にお問い合わせください。"
    )
    assert repository.saved_answer_runs == []
    assert artifact_saver.requests
    assert trace_logger.records[0].stage == "answer.adoption"
    assert "保存済み成果物領域" in trace_logger.records[0].diagnostic_message


def test_execute_chat_run_marks_error_and_traces_generation_failure() -> None:
    """
    観点：チャット実行ユースケースが生成用Codex失敗を利用者向け終端と調査ログへ変換すること
    確認：Codex起動失敗ではrunをerrorへ更新し、answer保存を行わず、
    traceログにrun IDとstageを含む診断を残すこと
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    class FailingGenerationRunner(FakeCodexGenerationRunner):
        """生成用Codex起動失敗を再現するFake。"""

        def run_generation(
            self,
            request: CodexGenerationRequest,
        ) -> CodexGenerationResult:
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="生成用Codexの起動に失敗しました。",
            )

    repository = FakeChatExecutionRepository()
    trace_logger = FakeTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=FailingGenerationRunner(results=[]),
        answer_validator=FakeAnswerValidator(results=[]),
        adopted_artifact_saver=FakeAdoptedArtifactSaver(),
        event_publisher=FakeRunEventPublisher(),
        clock=FixedClock(),
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert repository.states[-1].state == RunState.ERROR.value
    assert repository.saved_answer_runs == []
    assert trace_logger.records[0].stage == "codex.generation"
    assert "生成用Codex" in trace_logger.records[0].diagnostic_message


def test_execute_chat_run_returns_without_side_effect_when_context_missing(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが対象run不在時に副作用を出さないこと
    確認：runtime contextを取得できない場合はCodex実行、状態更新、traceを
    行わず終了すること
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository(runtime_context=None)
    generation_runner = FakeCodexGenerationRunner(results=[generation_result(tmp_path)])
    trace_logger = FakeTraceLogger()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=generation_runner,
        answer_validator=FakeAnswerValidator(results=[]),
        adopted_artifact_saver=FakeAdoptedArtifactSaver(),
        event_publisher=FakeRunEventPublisher(),
        clock=FixedClock(),
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert repository.states == []
    assert generation_runner.requests == []
    assert trace_logger.records == []


def test_execute_chat_run_accepts_enum_status_and_uuid_artifact_id(
    tmp_path: Path,
) -> None:
    """
    観点：チャット実行ユースケースが型付き検証結果と保存済み成果物IDを
    DB DTOへ変換すること
    確認：ValidationStatus enumのacceptedとUUID型artifact_idでもcompletedへ遷移し、
    回答保存まで完了すること
    """
    from backend.application.execution.execute_chat_run import (
        ExecuteChatRunCommand,
        ExecuteChatRunUseCase,
    )

    repository = FakeChatExecutionRepository()
    validator = FakeAnswerValidator(
        results=[
            ValidationResultRecord(
                status=ValidationStatus.ACCEPTED,
                answer=ValidatedAnswer(
                    blocks=(
                        ValidatedBlock(
                            markdown="![図](artifacts/diagram.svg)",
                            references=(),
                            artifact_links=("artifacts/diagram.svg",),
                        ),
                    ),
                ),
            ),
        ],
    )
    artifact_saver = UuidAdoptedArtifactSaver()
    use_case = ExecuteChatRunUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        generation_runner=FakeCodexGenerationRunner(
            results=[generation_result(tmp_path)],
        ),
        answer_validator=validator,
        adopted_artifact_saver=artifact_saver,
        event_publisher=FakeRunEventPublisher(),
        clock=FixedClock(),
        trace_logger=FakeTraceLogger(),
    )

    use_case.execute(
        ExecuteChatRunCommand(
            chat_id=CHAT_ID_VALUE,
            run_id=RUN_ID_VALUE,
            trace_id="trace-f005",
        ),
    )

    assert repository.states[-1].state == RunState.COMPLETED.value
    assert repository.saved_answer_markdown == [
        "![図](/api/artifacts/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa)",
    ]
    assert artifact_saver.requests

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from backend.application.artifacts.save_adopted_artifacts import (
    SaveAdoptedArtifactsUseCase,
)
from backend.application.execution.dto import CodexCancelResult
from backend.application.execution.execute_chat_run import (
    ExecuteChatRunCommand,
    ExecuteChatRunUseCase,
)
from backend.application.execution.run_event_broker import (
    RunEvent,
    RunEventBroker,
    RunEventType,
)
from backend.application.ports.runtime.interface import (
    BackgroundExecutorPort,
    RunDispatchResult,
    RunDispatchStatus,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.validation.validate_answer import ValidateAnswerUseCase
from backend.infrastructure.codex.codex_runner import CodexRunner, CodexRunnerSettings
from backend.infrastructure.config.settings import AppSettings
from backend.infrastructure.database.repositories.chat import SqlAlchemyChatRepository
from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)
from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
from backend.infrastructure.filesystem.reference_file_validator import (
    PdfReferenceFileValidator,
)
from backend.infrastructure.runtime.clock import SystemClock
from backend.infrastructure.trace_log.writer import TraceLogWriter
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId


class ChatRunExecutorLike(Protocol):
    """dispatcherから呼び出すrun実行本体。"""

    def execute(self, chat_id: UUID, run_id: UUID, trace_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class NullRunExecutionDispatcher:
    """F003受付境界だけを成立させるrun登録スタブ。"""

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> RunDispatchResult:
        return RunDispatchResult(status=RunDispatchStatus.REGISTERED.value)


@dataclass(slots=True)
class InProcessRunExecutionDispatcher:
    """同一プロセス内のbackground実行へrunを登録するdispatcher。"""

    background_executor: BackgroundExecutorPort
    _registered_run_ids: set[UUID] = field(default_factory=set)

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> RunDispatchResult:
        if run_id in self._registered_run_ids:
            return RunDispatchResult(
                status=RunDispatchStatus.ALREADY_REGISTERED.value,
            )
        if not self.background_executor.submit(run_id):
            return RunDispatchResult(
                status=RunDispatchStatus.FAILED.value,
                diagnostic_message="runのbackground登録に失敗しました。",
            )
        self._registered_run_ids.add(run_id)
        return RunDispatchResult(status=RunDispatchStatus.REGISTERED.value)


@dataclass(slots=True)
class ThreadedRunExecutionDispatcher:
    """受付済みrunを別スレッドの実行本体へ登録するdispatcher。"""

    executor: ChatRunExecutorLike
    max_workers: int = 4
    _registered_run_ids: set[UUID] = field(default_factory=set)
    _thread_pool: ThreadPoolExecutor = field(init=False)

    def __post_init__(self) -> None:
        self._thread_pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="d-concierge-run",
        )

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> RunDispatchResult:
        if run_id in self._registered_run_ids:
            return RunDispatchResult(
                status=RunDispatchStatus.ALREADY_REGISTERED.value,
            )
        try:
            self._thread_pool.submit(self.executor.execute, chat_id, run_id, trace_id)
        except RuntimeError as error:
            return RunDispatchResult(
                status=RunDispatchStatus.FAILED.value,
                diagnostic_message=str(error),
            )
        self._registered_run_ids.add(run_id)
        return RunDispatchResult(status=RunDispatchStatus.REGISTERED.value)


@dataclass(frozen=True, slots=True)
class DatabaseChatRunExecutor:
    """DBセッションを開き、F005チャット実行ユースケースを組み立てる。"""

    session_factory: sessionmaker[Session]
    settings: AppSettings
    run_event_broker: RunEventBroker
    trace_log_writer: TraceLogWriter
    script_path: Path
    codex_runner: CodexRunner | None = None

    def execute(self, chat_id: UUID, run_id: UUID, trace_id: str) -> None:
        saved_artifacts_dir = self.settings.generator.saved_artifacts_dir
        if saved_artifacts_dir is None:
            raise RuntimeError("generator.saved_artifacts_dir が未設定です。")
        with self.session_factory() as session:
            repository = SqlAlchemyChatRepository(session)
            codex_runner = self.codex_runner or create_codex_runner(
                self.settings,
                self.script_path,
            )
            trace_logger = _ExecutionTraceLogger(
                writer=self.trace_log_writer,
                trace_id=trace_id,
                chat_id=chat_id,
                run_id=run_id,
            )
            use_case = ExecuteChatRunUseCase(
                repository=repository,
                transaction_manager=SqlAlchemyTransactionManager(session),
                generation_runner=codex_runner,
                answer_validator=ValidateAnswerUseCase(
                    reference_validator=PdfReferenceFileValidator(
                        self.settings.data_source.dir,
                    ),
                    validator_runner=codex_runner,
                    validator_output_max_retries=self.settings.validator.max_retries,
                ),
                adopted_artifact_saver=SaveAdoptedArtifactsUseCase(
                    artifact_store=FileArtifactStore(
                        saved_artifacts_dir,
                    ),
                ),
                event_publisher=_RunEventBrokerPublisher(self.run_event_broker),
                clock=SystemClock(self.settings.app.timezone),
                trace_logger=trace_logger,
                execution_deadline_seconds=self.settings.server.timeout_seconds,
                max_regenerations=self.settings.generator.max_retries,
            )
            use_case.execute(
                ExecuteChatRunCommand(
                    chat_id=chat_id,
                    run_id=run_id,
                    trace_id=trace_id,
                )
            )


@dataclass(frozen=True, slots=True)
class _RunEventBrokerPublisher:
    broker: RunEventBroker

    def publish_state(self, run_id: UUID, state: str) -> None:
        self.broker.publish(RunEvent.state(run_id, state))

    def publish_message(self, run_id: UUID, text: str) -> None:
        self.broker.publish(RunEvent.message(run_id, text))

    def publish_answer(self, run_id: UUID) -> None:
        self.broker.publish(
            RunEvent.end(
                event_type=RunEventType.ANSWER,
                run_id=run_id,
                state="completed",
                user_message="",
            )
        )

    def publish_error(self, run_id: UUID, state: str) -> None:
        event_type = (
            RunEventType.CANCELED if state == "canceled" else RunEventType.ERROR
        )
        self.broker.publish(
            RunEvent.end(
                event_type=event_type,
                run_id=run_id,
                state=state,
                user_message="",
            )
        )


@dataclass(frozen=True, slots=True)
class _ExecutionTraceLogger:
    writer: TraceLogWriter
    trace_id: str
    chat_id: UUID
    run_id: UUID

    def write_trace(self, stage: str, diagnostic_message: str) -> None:
        self.writer.write(
            TraceLogRecord(
                occurred_at=datetime.now(UTC),
                trace_id=TraceId(self.trace_id),
                event_name="chat_run_execution_failed",
                stage=stage,
                error_type=ErrorType.SYSTEM,
                message=diagnostic_message,
                exception_type="",
                stacktrace="",
                http_method="",
                path="background",
                status_code=0,
                chat_id=str(self.chat_id),
                run_id=str(self.run_id),
            )
        )


@dataclass(frozen=True, slots=True)
class AcceptedRunBackgroundExecutor:
    """F004時点ではaccepted runを登録済みとして扱うbackground境界。"""

    def submit(self, run_id: UUID) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class NoopCodexRunCancellation:
    """F005以降のCodex実行本体へ依存しないキャンセル境界。"""

    def cancel(self, chat_id: UUID, run_id: UUID, trace_id: str) -> CodexCancelResult:
        return CodexCancelResult(status="sent")


def create_codex_runner(settings: AppSettings, script_path: Path) -> CodexRunner:
    """実行・キャンセルで共有するCodexRunnerを生成する。"""

    return CodexRunner(_codex_settings(settings, script_path))


def _codex_settings(settings: AppSettings, script_path: Path) -> CodexRunnerSettings:
    return CodexRunnerSettings(
        script_path=script_path,
        generator_home=settings.generator.home,
        validator_home=settings.validator.home,
        generator_workdir_root=settings.generator.workdir,
        validator_workdir_root=settings.validator.workdir,
        data_source_dir=settings.data_source.dir,
        output_schema_dir=settings.generator.output_schema.parent,
        generator_schema_file=settings.generator.output_schema.name,
        validator_schema_file=settings.validator.output_schema.name,
    )

from uuid import UUID

from backend.application.ports.codex.interface import CancelRequesterPort
from backend.application.ports.database.dto import ChatDeletionRun, ChatDeletionTarget
from backend.application.ports.database.interface import (
    ChatDeletionRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.filesystem.interface import (
    SavedArtifactDeletionPort,
    SessionWorkdirCleanupPort,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.ports.trace_log.interface import TraceLoggerPort
from backend.application.transactions import NoopTransactionManager
from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError, ChatNotFoundError
from backend.shared.tracing.exception import exception_message, exception_stacktrace
from backend.shared.user_messages import CANCELED_MESSAGE


class ExecuteChatDeletionUseCase:
    """削除中チャットの物理削除を調停する。"""

    def __init__(
        self,
        repository: ChatDeletionRepositoryPort,
        cancel_requester: CancelRequesterPort | None,
        session_workdir_cleanup: SessionWorkdirCleanupPort,
        artifact_deletion: SavedArtifactDeletionPort,
        transaction_manager: TransactionManagerPort | None = None,
        trace_logger: TraceLoggerPort | None = None,
    ) -> None:
        self._repository = repository
        self._cancel_requester = cancel_requester
        self._session_workdir_cleanup = session_workdir_cleanup
        self._artifact_deletion = artifact_deletion
        self._trace_logger = trace_logger
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, chat_id: UUID, trace_id: str = "") -> None:
        """対象チャットの物理削除を進める。"""
        try:
            with self._transaction_manager.transaction():
                target = self._repository.get_chat_deletion_target(chat_id)
        except ChatNotFoundError:
            return

        if target.unfinished_runs:
            self._handle_unfinished_runs(target, trace_id)
            return

        try:
            self._session_workdir_cleanup.delete_session_workdirs(
                target.user_id,
                target.session_id,
            )
            self._artifact_deletion.delete_saved_artifacts(
                target.artifact_storage_paths
            )
            with self._transaction_manager.transaction():
                self._repository.delete_chat_cascade(chat_id)
        except Exception as exc:
            self._write_failure_trace(chat_id, trace_id, "chat_deletion_failed", exc)

    def _handle_unfinished_runs(
        self, target: ChatDeletionTarget, trace_id: str
    ) -> None:
        try:
            for run in target.unfinished_runs:
                self._request_or_complete_cancel(target.chat_id, run)
        except Exception as exc:
            self._write_failure_trace(
                target.chat_id,
                trace_id,
                "chat_deletion_cancel_failed",
                exc,
            )

    def _request_or_complete_cancel(self, chat_id: UUID, run: ChatDeletionRun) -> None:
        if run.state is RunState.ACCEPTED:
            with self._transaction_manager.transaction():
                self._repository.set_run_state(
                    chat_id,
                    run.run_id,
                    RunState.CANCELED,
                    CANCELED_MESSAGE,
                )
            return
        if run.state in {RunState.RUNNING, RunState.VALIDATING}:
            if self._cancel_requester is not None:
                self._cancel_requester.request_cancel(run.run_id)

    def _write_failure_trace(
        self, chat_id: UUID, trace_id: str, event_name: str, exc: Exception
    ) -> None:
        if self._trace_logger is None:
            return
        if isinstance(exc, AppError):
            error_type = exc.error_type.value
        else:
            error_type = ErrorType.SYSTEM.value
        diagnostic_message = (
            exc.diagnostic_message
            if isinstance(exc, AppError)
            else exception_message(exc)
        )
        self._trace_logger.write(
            TraceLogRecord(
                trace_id=trace_id,
                event_name=event_name,
                stage="chat_deletion",
                chat_id=chat_id,
                error_type=error_type,
                exception_type=type(exc).__name__,
                stacktrace=exception_stacktrace(exc),
                message=diagnostic_message,
            )
        )

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from traceback import format_exception
from typing import Protocol
from uuid import UUID

from backend.application.chat.dto import DeleteChatResult
from backend.application.ports.database.dto import ChatDeletionTarget
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.domain.chat.chat_state import ChatState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId


class ChatDeletionRepositoryLike(Protocol):
    """チャット削除で使うDB境界。"""

    def mark_chat_deleting(
        self,
        user_id: str,
        chat_id: UUID,
        updated_at: datetime,
    ) -> str | None: ...

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget | None: ...

    def delete_chat_cascade(self, chat_id: UUID) -> None: ...


class ClockLike(Protocol):
    """現在時刻境界。"""

    def now_utc(self) -> datetime: ...


class TraceLoggerLike(Protocol):
    """TraceLogRecord保存境界。"""

    def write(self, record: TraceLogRecord) -> Path | None: ...


class DispatchResultLike(Protocol):
    """削除ジョブ登録結果の最小契約。"""

    @property
    def status(self) -> str: ...

    @property
    def diagnostic_message(self) -> str: ...


class ChatDeletionDispatcherLike(Protocol):
    """チャット物理削除ジョブ登録境界。"""

    def dispatch_chat_deletion(
        self,
        chat_id: UUID,
        trace_id: str,
    ) -> DispatchResultLike: ...


class CancelRequesterLike(Protocol):
    """未完了run終了要求境界。"""

    def cancel(self, run_id: UUID, trace_id: str) -> str: ...


class SessionWorkdirCleanupLike(Protocol):
    """Codexセッション作業領域削除境界。"""

    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None: ...


class SavedArtifactDeletionLike(Protocol):
    """保存済み成果物削除境界。"""

    def delete_saved_files(self, storage_paths: tuple[str, ...]) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class DeleteChatCommand:
    """チャット削除受付要求。"""

    authenticated_user_id: str
    chat_id: UUID
    trace_id: TraceId


@dataclass(frozen=True, slots=True)
class ExecuteChatDeletionCommand:
    """チャット物理削除要求。"""

    chat_id: UUID
    trace_id: TraceId


class DeleteChatUseCase:
    """チャット削除受付を調停する。"""

    def __init__(
        self,
        *,
        repository: ChatDeletionRepositoryLike,
        transaction_manager: TransactionManagerPort,
        dispatcher: ChatDeletionDispatcherLike,
        trace_logger: TraceLoggerLike,
        clock: ClockLike,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._dispatcher = dispatcher
        self._trace_logger = trace_logger
        self._clock = clock

    def execute(self, command: DeleteChatCommand) -> DeleteChatResult:
        """対象チャットをdeletingへ更新し、物理削除ジョブを登録する。"""

        with self._transaction_manager:
            chat_state = self._repository.mark_chat_deleting(
                command.authenticated_user_id,
                command.chat_id,
                self._clock.now_utc(),
            )
        if chat_state is None:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="対象チャットが見つかりません。",
            )

        result = self._dispatcher.dispatch_chat_deletion(
            command.chat_id,
            str(command.trace_id),
        )
        if result.status == "failed":
            _write_trace_safely(
                self._trace_logger,
                TraceLogRecord(
                    occurred_at=datetime.now(UTC),
                    trace_id=command.trace_id,
                    event_name="chat_deletion_dispatch_failed",
                    stage="application.chat.delete_chat",
                    error_type=ErrorType.SYSTEM,
                    message=result.diagnostic_message,
                    exception_type="ChatDeletionDispatchFailed",
                    stacktrace="",
                    http_method="",
                    path="background",
                    status_code=0,
                    chat_id=str(command.chat_id),
                ),
            )

        return DeleteChatResult(
            chat_id=command.chat_id,
            chat_state=ChatState.DELETING.value,
        )


class ExecuteChatDeletionUseCase:
    """チャット物理削除を調停する。"""

    def __init__(
        self,
        *,
        repository: ChatDeletionRepositoryLike,
        cancel_requester: CancelRequesterLike,
        workdir_cleanup: SessionWorkdirCleanupLike,
        artifact_deletion: SavedArtifactDeletionLike,
        trace_logger: TraceLoggerLike,
    ) -> None:
        self._repository = repository
        self._cancel_requester = cancel_requester
        self._workdir_cleanup = workdir_cleanup
        self._artifact_deletion = artifact_deletion
        self._trace_logger = trace_logger

    def execute(self, command: ExecuteChatDeletionCommand) -> None:
        """ファイル削除完了後にDB上のチャット一式を削除する。"""

        target = self._repository.get_chat_deletion_target(command.chat_id)
        if target is None:
            return
        if target.unfinished_run_ids:
            for run_id in target.unfinished_run_ids:
                self._cancel_requester.cancel(run_id, str(command.trace_id))
            return

        try:
            self._workdir_cleanup.delete_session_workdirs(
                target.user_id,
                target.session_id,
            )
            self._artifact_deletion.delete_saved_files(target.storage_paths)
            self._repository.delete_chat_cascade(target.chat_id)
        except Exception as error:
            _write_physical_failure(
                trace_logger=self._trace_logger,
                event_name="chat_physical_deletion_failed",
                stage="application.chat.execute_chat_deletion",
                trace_id=command.trace_id,
                message=str(error),
                error=error,
                chat_id=command.chat_id,
                user_id=None,
            )


def _write_physical_failure(
    *,
    trace_logger: TraceLoggerLike,
    event_name: str,
    stage: str,
    trace_id: TraceId,
    message: str,
    error: Exception,
    chat_id: UUID | None,
    user_id: str | None,
) -> None:
    _write_trace_safely(
        trace_logger,
        TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=trace_id,
            event_name=event_name,
            stage=stage,
            error_type=ErrorType.SYSTEM,
            message=message,
            exception_type=type(error).__name__,
            stacktrace="".join(
                format_exception(type(error), error, error.__traceback__),
            ),
            http_method="",
            path="background",
            status_code=0,
            user_id=user_id,
            chat_id=str(chat_id) if chat_id is not None else None,
        ),
    )


def _write_trace_safely(
    trace_logger: TraceLoggerLike,
    record: TraceLogRecord,
) -> None:
    try:
        trace_logger.write(record)
    except Exception:
        return

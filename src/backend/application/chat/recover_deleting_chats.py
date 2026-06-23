from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from traceback import format_exception
from typing import Protocol
from uuid import UUID

from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId


class ChatRecoveryRepositoryLike(Protocol):
    """起動時チャット削除回復で使うDB境界。"""

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]: ...


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


@dataclass(frozen=True, slots=True)
class RecoverDeletingChatsCommand:
    """起動時チャット削除回復要求。"""

    trace_id: TraceId


@dataclass(frozen=True, slots=True)
class RecoverDeletingChatsResult:
    """起動時チャット削除回復結果。"""

    deleting_chats_registered: int
    deleting_chats_failed: int


class RecoverDeletingChatsUseCase:
    """deletingチャットの物理削除ジョブを起動時に再登録する。"""

    def __init__(
        self,
        *,
        repository: ChatRecoveryRepositoryLike,
        dispatcher: ChatDeletionDispatcherLike,
        trace_logger: TraceLoggerLike,
    ) -> None:
        self._repository = repository
        self._dispatcher = dispatcher
        self._trace_logger = trace_logger

    def execute(
        self,
        command: RecoverDeletingChatsCommand,
    ) -> RecoverDeletingChatsResult:
        """削除中チャットを取得し、物理削除ジョブへ再登録する。"""

        deleting_chat_ids = self._repository.list_deleting_chats_for_recovery()
        registered_count = 0
        failed_count = 0
        for chat_id in deleting_chat_ids:
            try:
                result = self._dispatcher.dispatch_chat_deletion(
                    chat_id,
                    str(command.trace_id),
                )
            except Exception as error:
                failed_count += 1
                _write_recovery_exception(
                    trace_logger=self._trace_logger,
                    trace_id=command.trace_id,
                    chat_id=chat_id,
                    message=f"チャット削除ジョブ登録中に例外が発生しました: {error}",
                    error=error,
                )
                continue
            if result.status == "failed":
                failed_count += 1
                _write_recovery_failure(
                    trace_logger=self._trace_logger,
                    trace_id=command.trace_id,
                    chat_id=chat_id,
                    message=result.diagnostic_message,
                )
                continue
            registered_count += 1

        return RecoverDeletingChatsResult(
            deleting_chats_registered=registered_count,
            deleting_chats_failed=failed_count,
        )


def _write_recovery_failure(
    *,
    trace_logger: TraceLoggerLike,
    trace_id: TraceId,
    chat_id: UUID,
    message: str,
) -> None:
    _write_trace_safely(
        trace_logger,
        TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=trace_id,
            event_name="chat_deletion_recovery_failed",
            stage="application.chat.recover_deleting_chats",
            error_type=ErrorType.SYSTEM,
            message=message,
            exception_type="ChatDeletionDispatchFailed",
            stacktrace="",
            http_method="",
            path="startup",
            status_code=0,
            chat_id=str(chat_id),
        ),
    )


def _write_recovery_exception(
    *,
    trace_logger: TraceLoggerLike,
    trace_id: TraceId,
    chat_id: UUID,
    message: str,
    error: Exception,
) -> None:
    _write_trace_safely(
        trace_logger,
        TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=trace_id,
            event_name="chat_deletion_recovery_failed",
            stage="application.chat.recover_deleting_chats",
            error_type=ErrorType.SYSTEM,
            message=message,
            exception_type=type(error).__name__,
            stacktrace="".join(
                format_exception(type(error), error, error.__traceback__),
            ),
            http_method="",
            path="startup",
            status_code=0,
            chat_id=str(chat_id),
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

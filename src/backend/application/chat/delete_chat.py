from uuid import UUID

from backend.application.ports.database.dto import DeleteChatResult
from backend.application.ports.database.interface import (
    ChatDeletionRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.interface import ChatDeletionDispatcherPort
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.ports.trace_log.interface import TraceLoggerPort
from backend.application.transactions import NoopTransactionManager
from backend.domain.chat.chat_state import ChatState
from backend.shared.errors.error_type import ErrorType


class DeleteChatUseCase:
    """チャット削除要求の受付を調停する。"""

    def __init__(
        self,
        repository: ChatDeletionRepositoryPort,
        deletion_dispatcher: ChatDeletionDispatcherPort | None,
        transaction_manager: TransactionManagerPort | None = None,
        trace_logger: TraceLoggerPort | None = None,
    ) -> None:
        self._repository = repository
        self._deletion_dispatcher = deletion_dispatcher
        self._trace_logger = trace_logger
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, chat_id: UUID, trace_id: str) -> DeleteChatResult:
        """対象チャットを削除中にし、物理削除ジョブを登録する。"""
        with self._transaction_manager.transaction():
            result = self._repository.mark_chat_deleting(chat_id)

        if self._deletion_dispatcher is None:
            return result

        dispatch = self._deletion_dispatcher.register(chat_id, trace_id)
        if dispatch.status is DispatchStatus.FAILED:
            self._write_dispatch_failure(chat_id, trace_id, dispatch.failure_reason)
        return result

    def _write_dispatch_failure(
        self, chat_id: UUID, trace_id: str, failure_reason: str | None
    ) -> None:
        if self._trace_logger is None:
            return
        self._trace_logger.write(
            TraceLogRecord(
                trace_id=trace_id,
                event_name="chat_deletion_dispatch_failed",
                stage="chat_deletion_acceptance",
                chat_id=chat_id,
                error_type=ErrorType.SYSTEM.value,
                process_result=failure_reason,
                message="チャット物理削除ジョブの登録に失敗しました。",
            )
        )


def deleting_chat_result(chat_id: UUID) -> DeleteChatResult:
    """削除受付応答を生成する。"""
    return DeleteChatResult(chat_id=chat_id, chat_state=ChatState.DELETING)

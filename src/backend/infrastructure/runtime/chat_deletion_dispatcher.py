from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from uuid import UUID

from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.dto import DispatchResult
from backend.application.ports.runtime.interface import (
    BackgroundExecutorPort,
    ChatDeletionExecutorPort,
)


class InProcessChatDeletionDispatcher:
    """アプリ内スレッドで削除中チャットの物理削除を実行するdispatcher。"""

    def __init__(
        self,
        deletion_executor: ChatDeletionExecutorPort,
        background_executor: BackgroundExecutorPort | None = None,
    ) -> None:
        self._deletion_executor = deletion_executor
        self._background_executor = (
            background_executor
            if background_executor is not None
            else ThreadPoolExecutor(max_workers=2, thread_name_prefix="chat-delete")
        )
        self._active_chat_ids: set[UUID] = set()
        self._lock = RLock()

    def register(self, chat_id: UUID, trace_id: str) -> DispatchResult:
        """削除中チャットをバックグラウンド実行へ登録する。"""
        with self._lock:
            if chat_id in self._active_chat_ids:
                return DispatchResult(status=DispatchStatus.ALREADY_REGISTERED)
            self._active_chat_ids.add(chat_id)

        try:
            self._background_executor.submit(
                lambda: self._execute_and_release(chat_id, trace_id)
            )
        except RuntimeError as exc:
            self._release(chat_id)
            return DispatchResult(status=DispatchStatus.FAILED, failure_reason=str(exc))
        return DispatchResult(status=DispatchStatus.REGISTERED)

    def _execute_and_release(self, chat_id: UUID, trace_id: str) -> None:
        try:
            self._deletion_executor.execute(chat_id, trace_id)
        finally:
            self._release(chat_id)

    def _release(self, chat_id: UUID) -> None:
        with self._lock:
            self._active_chat_ids.discard(chat_id)

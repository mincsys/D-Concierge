from concurrent.futures import ThreadPoolExecutor
from threading import RLock

from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.dto import DispatchResult
from backend.application.ports.runtime.interface import (
    AccountDeletionExecutorPort,
    BackgroundExecutorPort,
)


class InProcessAccountDeletionDispatcher:
    """アプリ内スレッドで削除中アカウントの物理削除を実行するdispatcher。"""

    def __init__(
        self,
        deletion_executor: AccountDeletionExecutorPort,
        background_executor: BackgroundExecutorPort | None = None,
    ) -> None:
        self._deletion_executor = deletion_executor
        self._background_executor = (
            background_executor
            if background_executor is not None
            else ThreadPoolExecutor(max_workers=2, thread_name_prefix="account-delete")
        )
        self._active_user_ids: set[str] = set()
        self._lock = RLock()

    def register(self, user_id: str, trace_id: str) -> DispatchResult:
        """削除中アカウントをバックグラウンド実行へ登録する。"""
        with self._lock:
            if user_id in self._active_user_ids:
                return DispatchResult(status=DispatchStatus.ALREADY_REGISTERED)
            self._active_user_ids.add(user_id)

        try:
            self._background_executor.submit(
                lambda: self._execute_and_release(user_id, trace_id)
            )
        except RuntimeError as exc:
            self._release(user_id)
            return DispatchResult(status=DispatchStatus.FAILED, failure_reason=str(exc))
        return DispatchResult(status=DispatchStatus.REGISTERED)

    def _execute_and_release(self, user_id: str, trace_id: str) -> None:
        try:
            self._deletion_executor.execute(user_id, trace_id)
        finally:
            self._release(user_id)

    def _release(self, user_id: str) -> None:
        with self._lock:
            self._active_user_ids.discard(user_id)

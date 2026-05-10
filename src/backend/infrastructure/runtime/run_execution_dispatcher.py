from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from uuid import UUID

from backend.application.ports.runtime.dto import DispatchResult
from backend.application.ports.runtime.interface import (
    BackgroundExecutorPort,
    ChatRunExecutorPort,
)


class InProcessRunExecutionDispatcher:
    """アプリ内スレッドで受付済みrunを実行するdispatcher。"""

    def __init__(
        self,
        run_executor: ChatRunExecutorPort,
        background_executor: BackgroundExecutorPort | None = None,
    ) -> None:
        self._run_executor = run_executor
        self._background_executor = (
            background_executor
            if background_executor is not None
            else ThreadPoolExecutor(max_workers=3, thread_name_prefix="chat-run")
        )
        self._active_run_ids: set[UUID] = set()
        self._lock = RLock()

    def register(self, chat_id: UUID, run_id: UUID, trace_id: str) -> DispatchResult:
        """受付済みrunをバックグラウンド実行へ登録する。"""
        with self._lock:
            if run_id in self._active_run_ids:
                return DispatchResult(status="already_registered")
            self._active_run_ids.add(run_id)

        try:
            self._background_executor.submit(
                lambda: self._execute_and_release(chat_id, run_id, trace_id)
            )
        except RuntimeError as exc:
            self._release(run_id)
            return DispatchResult(status="failed", failure_reason=str(exc))
        return DispatchResult(status="registered")

    def _execute_and_release(self, chat_id: UUID, run_id: UUID, trace_id: str) -> None:
        try:
            self._run_executor.execute(chat_id, run_id, trace_id)
        finally:
            self._release(run_id)

    def _release(self, run_id: UUID) -> None:
        with self._lock:
            self._active_run_ids.discard(run_id)

from collections.abc import Callable
from concurrent.futures import Future
from typing import Protocol
from uuid import UUID

from backend.application.ports.runtime.dto import DispatchResult


class ChatRunExecutorPort(Protocol):
    """チャット実行ユースケース境界。"""

    def execute(self, chat_id: UUID, run_id: UUID) -> None:
        """指定runを実行する。"""


class BackgroundExecutorPort(Protocol):
    """バックグラウンド実行基盤境界。"""

    def submit(self, task: Callable[[], None]) -> Future[None]:
        """実行タスクを登録する。"""


class RunExecutionDispatcherPort(Protocol):
    """受付済みrunをバックグラウンド登録する境界。"""

    def register(self, chat_id: UUID, run_id: UUID) -> DispatchResult:
        """対象runの実行を登録する。"""

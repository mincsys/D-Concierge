from collections.abc import Callable
from concurrent.futures import Future
from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.application.ports.runtime.dto import DispatchResult


class ChatRunExecutorPort(Protocol):
    """チャット実行ユースケース境界。"""

    def execute(self, chat_id: UUID, run_id: UUID, trace_id: str = "") -> None:
        """指定runを実行する。"""


class ChatDeletionExecutorPort(Protocol):
    """チャット物理削除ユースケース境界。"""

    def execute(self, chat_id: UUID, trace_id: str = "") -> None:
        """指定チャットを物理削除する。"""


class BackgroundExecutorPort(Protocol):
    """バックグラウンド実行基盤境界。"""

    def submit(self, task: Callable[[], None]) -> Future[None]:
        """実行タスクを登録する。"""


class ClockPort(Protocol):
    """現在時刻取得境界。"""

    def now(self) -> datetime:
        """タイムゾーン付き現在日時を返す。"""

    def now_utc(self) -> datetime:
        """タイムゾーン付きUTC現在日時を返す。"""

    def now_app_timezone(self) -> datetime:
        """アプリタイムゾーンの現在日時を返す。"""


class IdGeneratorPort(Protocol):
    """UUID発番境界。"""

    def new_uuid(self) -> UUID:
        """新しいUUIDを返す。"""


class UuidGeneratorPort(IdGeneratorPort, Protocol):
    """UUID発番境界の互換名。"""


class RunExecutionDispatcherPort(Protocol):
    """受付済みrunをバックグラウンド登録する境界。"""

    def register(self, chat_id: UUID, run_id: UUID, trace_id: str) -> DispatchResult:
        """対象runの実行を登録する。"""


class ChatDeletionDispatcherPort(Protocol):
    """削除中チャットをバックグラウンド登録する境界。"""

    def register(self, chat_id: UUID, trace_id: str) -> DispatchResult:
        """対象チャットの物理削除を登録する。"""

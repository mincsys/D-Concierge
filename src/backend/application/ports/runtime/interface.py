from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID


class ClockPort(Protocol):
    """現在時刻取得境界。"""

    def now_utc(self) -> datetime: ...

    def now_app_timezone(self) -> datetime: ...


class IdGeneratorPort(Protocol):
    """UUIDv7発番境界。"""

    def new_uuid(self) -> UUID: ...


class UuidGeneratorPort(IdGeneratorPort, Protocol):
    """UUID発番用途を明示する派生境界。"""


class AccountDeletionDispatchStatus(Enum):
    """アカウント物理削除ジョブ登録結果。"""

    REGISTERED = "registered"
    ALREADY_REGISTERED = "already_registered"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AccountDeletionDispatchResult:
    """アカウント物理削除ジョブ登録結果DTO。"""

    status: str
    diagnostic_message: str = ""


class AccountDeletionDispatcherPort(Protocol):
    """アカウント物理削除ジョブ登録依頼境界。"""

    def dispatch_account_deletion(
        self,
        user_id: str,
        trace_id: str,
    ) -> AccountDeletionDispatchResult: ...


class AccountDeletionExecutorPort(Protocol):
    """アカウント物理削除ジョブ実行本体境界。"""

    def execute(self, user_id: str, trace_id: str) -> None: ...


class ChatDeletionDispatchStatus(Enum):
    """チャット物理削除ジョブ登録結果。"""

    REGISTERED = "registered"
    ALREADY_REGISTERED = "already_registered"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ChatDeletionDispatchResult:
    """チャット物理削除ジョブ登録結果DTO。"""

    status: str
    diagnostic_message: str = ""


class ChatDeletionDispatcherPort(Protocol):
    """チャット物理削除ジョブ登録依頼境界。"""

    def dispatch_chat_deletion(
        self,
        chat_id: UUID,
        trace_id: str,
    ) -> ChatDeletionDispatchResult: ...


class RunDispatchStatus(Enum):
    """チャット実行処理の登録結果。"""

    REGISTERED = "registered"
    ALREADY_REGISTERED = "already_registered"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RunDispatchResult:
    """チャット実行処理の登録結果DTO。"""

    status: str
    diagnostic_message: str = ""


class RunExecutionDispatcherPort(Protocol):
    """受付済みrunの実行登録境界。"""

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> RunDispatchResult: ...


class ChatRunExecutorPort(Protocol):
    """登録済みrunの実行本体境界。"""

    def execute(self, chat_id: UUID, run_id: UUID, trace_id: str) -> None: ...


class BackgroundExecutorPort(Protocol):
    """run実行をbackgroundへ登録する境界。"""

    def submit(self, run_id: UUID) -> bool: ...

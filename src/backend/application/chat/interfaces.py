from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from backend.application.ports.database.dto import AcceptedRun, ChatDetail, HistoryItem
from backend.application.ports.runtime.interface import RunDispatchResult


@runtime_checkable
class RunExecutionDispatcherLike(Protocol):
    """受付済みrunの実行登録境界。"""

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> RunDispatchResult: ...


class StartChatRepositoryLike(Protocol):
    """新規チャット開始ユースケースが必要とするRepository境界。"""

    def create_chat_with_first_run(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
        session_id: UUID,
        title: str,
        user_instruction: str,
        trace_id: str,
        started_at: datetime,
    ) -> AcceptedRun: ...

    def mark_run_error(self, run_id: UUID, diagnostic_message: str) -> None: ...


class AppendChatRunRepositoryLike(Protocol):
    """継続指示受付ユースケースが必要とするRepository境界。"""

    def append_run(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        trace_id: str,
        started_at: datetime,
    ) -> AcceptedRun: ...

    def mark_run_error(self, run_id: UUID, diagnostic_message: str) -> None: ...


class ChatHistoryRepositoryLike(Protocol):
    """履歴一覧ユースケースが必要とするRepository境界。"""

    def list_histories(self, user_id: str) -> tuple[HistoryItem, ...]: ...


class ChatDetailRepositoryLike(Protocol):
    """履歴詳細ユースケースが必要とするRepository境界。"""

    def get_chat_detail(self, user_id: str, chat_id: UUID) -> ChatDetail | None: ...

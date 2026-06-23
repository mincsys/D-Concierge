from __future__ import annotations

from dataclasses import dataclass

from backend.application.chat.dto import HistoryItemResult, HistoryListResult
from backend.application.chat.interfaces import ChatHistoryRepositoryLike
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class ListChatHistoriesCommand:
    """履歴一覧取得要求。"""

    authenticated_user_id: str
    trace_id: TraceId


class ListChatHistoriesUseCase:
    """履歴一覧取得を調停する。"""

    def __init__(self, *, repository: ChatHistoryRepositoryLike) -> None:
        self._repository = repository

    def execute(self, command: ListChatHistoriesCommand) -> HistoryListResult:
        """ログインユーザの通常操作対象チャット一覧を返す。"""

        histories = self._repository.list_histories(command.authenticated_user_id)
        return HistoryListResult(
            items=tuple(
                HistoryItemResult(
                    chat_id=history.chat_id,
                    title=history.title,
                    latest_run_id=history.latest_run_id,
                    latest_state=history.latest_state,
                    updated_at=history.updated_at,
                )
                for history in histories
            ),
        )

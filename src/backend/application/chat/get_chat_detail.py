from uuid import UUID

from backend.application.ports.database.dto import ChatDetail
from backend.application.ports.database.interface import (
    ChatReadRepositoryPort,
    TransactionManagerPort,
)
from backend.application.transactions import NoopTransactionManager


class GetChatDetailUseCase:
    """チャット詳細取得を調停する。"""

    def __init__(
        self,
        repository: ChatReadRepositoryPort,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, chat_id: UUID, user_id: str = "") -> ChatDetail:
        """指定チャットの詳細を返す。"""
        with self._transaction_manager.transaction():
            return self._repository.get_chat_detail(chat_id, user_id=user_id)

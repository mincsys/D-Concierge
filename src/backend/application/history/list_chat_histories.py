from backend.application.ports.database.dto import HistoryItem
from backend.application.ports.database.interface import (
    ChatReadRepositoryPort,
    TransactionManagerPort,
)
from backend.application.transactions import NoopTransactionManager


class ListChatHistoriesUseCase:
    """履歴一覧取得を調停する。"""

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

    def execute(self) -> tuple[HistoryItem, ...]:
        """履歴一覧を返す。"""
        with self._transaction_manager.transaction():
            return self._repository.list_histories()

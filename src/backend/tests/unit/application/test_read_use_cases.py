from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from backend.application.chat.get_chat_detail import GetChatDetailUseCase
from backend.application.history.list_chat_histories import ListChatHistoriesUseCase
from backend.application.ports.database.dto import ChatDetail, HistoryItem
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_list_chat_histories_use_case_reads_with_transaction() -> None:
    """観点：履歴一覧取得UseCase。確認：明示トランザクション内で履歴一覧を取得する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("履歴")
    transaction_manager = RecordingTransactionManager()
    usecase = ListChatHistoriesUseCase(
        repository=repository,
        transaction_manager=transaction_manager,
    )

    histories = usecase.execute()

    assert isinstance(histories[0], HistoryItem)
    assert histories[0].chat_id == accepted.chat_id
    assert transaction_manager.completed_transactions == ["enter", "exit"]


def test_get_chat_detail_use_case_reads_with_transaction() -> None:
    """観点：履歴詳細取得UseCase。確認：明示トランザクション内でチャット詳細を取得する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("詳細")
    transaction_manager = RecordingTransactionManager()
    usecase = GetChatDetailUseCase(
        repository=repository,
        transaction_manager=transaction_manager,
    )

    detail = usecase.execute(accepted.chat_id)

    assert isinstance(detail, ChatDetail)
    assert detail.chat_id == accepted.chat_id
    assert transaction_manager.completed_transactions == ["enter", "exit"]


@dataclass(slots=True)
class RecordingTransactionManager:
    completed_transactions: list[str] = field(default_factory=list)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.completed_transactions.append("enter")
        try:
            yield
        finally:
            self.completed_transactions.append("exit")

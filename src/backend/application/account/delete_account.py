from datetime import UTC, datetime

from backend.application.account.common import transaction_manager_or_noop
from backend.application.ports.database.dto import AccountDeletionAccepted
from backend.application.ports.database.interface import (
    AccountRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import (
    AccountDeletionDispatcherPort,
    ClockPort,
)
from backend.domain.account.user_state import UserState


class DeleteAccountUseCase:
    """アカウント削除受付を調停する。"""

    def __init__(
        self,
        repository: AccountRepositoryPort,
        deletion_dispatcher: AccountDeletionDispatcherPort,
        transaction_manager: TransactionManagerPort | None = None,
        clock: ClockPort | None = None,
    ) -> None:
        self._repository = repository
        self._deletion_dispatcher = deletion_dispatcher
        self._transaction_manager = transaction_manager_or_noop(transaction_manager)
        self._clock = clock

    def execute(self, user_id: str, trace_id: str = "") -> AccountDeletionAccepted:
        """削除中化と全セッション削除を行い、物理削除を登録する。"""
        now = self._clock.now() if self._clock is not None else datetime.now(UTC)
        with self._transaction_manager.transaction():
            self._repository.mark_user_deleting(user_id, now)
            self._repository.mark_user_chats_deleting(user_id, now)
            self._repository.delete_sessions_by_user_id(user_id)
        self._deletion_dispatcher.register(user_id, trace_id)
        return AccountDeletionAccepted(account_state=UserState.DELETING)

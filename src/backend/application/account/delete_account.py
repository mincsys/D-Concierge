from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.application.account.dto import AccountStateResult
from backend.application.account.interfaces import AccountRepositoryLike
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import (
    AccountDeletionDispatcherPort,
    ClockPort,
)
from backend.shared.tracing.trace_id import TraceId


class AccountTraceLoggerLike(Protocol):
    """アカウントイベントのトレースログ境界。"""

    def write_account_event(
        self,
        event_name: str,
        user_id: str,
        trace_id: str,
        diagnostic_message: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class DeleteAccountCommand:
    """アカウント削除受付要求。"""

    authenticated_user_id: str
    trace_id: TraceId


class DeleteAccountUseCase:
    """アカウント削除受付を調停する。"""

    def __init__(
        self,
        *,
        repository: AccountRepositoryLike,
        transaction_manager: TransactionManagerPort,
        dispatcher: AccountDeletionDispatcherPort,
        trace_logger: AccountTraceLoggerLike,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._dispatcher = dispatcher
        self._trace_logger = trace_logger
        self._clock = clock

    def execute(self, command: DeleteAccountCommand) -> AccountStateResult:
        """削除受付状態へ更新し、非同期削除ジョブ登録を依頼する。"""

        now = self._clock.now_utc()
        with self._transaction_manager:
            account_state = self._repository.mark_user_deleting(
                command.authenticated_user_id,
                now,
            )
            self._repository.mark_user_chats_deleting(
                command.authenticated_user_id,
                now,
            )
            self._repository.delete_sessions_by_user_id(command.authenticated_user_id)

        result = self._dispatcher.dispatch_account_deletion(
            command.authenticated_user_id,
            str(command.trace_id),
        )
        if result.status == "failed":
            self._trace_logger.write_account_event(
                "account_deletion_dispatch_failed",
                command.authenticated_user_id,
                str(command.trace_id),
                result.diagnostic_message,
            )

        return AccountStateResult(account_state=account_state or "deleting")

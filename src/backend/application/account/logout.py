from __future__ import annotations

from dataclasses import dataclass

from backend.application.account.interfaces import AccountRepositoryLike
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.security.interface import SessionTokenProviderPort
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    """ログアウト要求。"""

    session_token: str | None
    trace_id: TraceId


class LogoutUseCase:
    """現在Cookieに対応するログインセッションを削除する。"""

    def __init__(
        self,
        *,
        repository: AccountRepositoryLike,
        transaction_manager: TransactionManagerPort,
        session_token_provider: SessionTokenProviderPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._session_token_provider = session_token_provider

    def execute(self, command: LogoutCommand) -> None:
        """Cookieがある場合だけ該当セッションを削除する。"""

        if command.session_token is None:
            return
        token_hash = self._session_token_provider.hash_token(command.session_token)
        with self._transaction_manager:
            self._repository.delete_session_by_token_hash(token_hash)

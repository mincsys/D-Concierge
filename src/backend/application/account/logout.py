from backend.application.account.common import transaction_manager_or_noop
from backend.application.ports.database.interface import (
    AccountRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.security.interface import SessionTokenProviderPort


class LogoutUseCase:
    """現在のログインセッション削除を調停する。"""

    def __init__(
        self,
        repository: AccountRepositoryPort,
        token_provider: SessionTokenProviderPort,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._token_provider = token_provider
        self._transaction_manager = transaction_manager_or_noop(transaction_manager)

    def execute(self, session_token: str | None, trace_id: str = "") -> None:
        """Cookieトークンに対応するセッションだけを削除する。"""
        _ = trace_id
        if session_token is None or session_token == "":
            return
        with self._transaction_manager.transaction():
            self._repository.delete_session_by_token_hash(
                self._token_provider.hash_token(session_token)
            )

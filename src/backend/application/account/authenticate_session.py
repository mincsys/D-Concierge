from backend.application.account.common import ClockPort, transaction_manager_or_noop
from backend.application.ports.database.dto import AuthenticatedUser
from backend.application.ports.database.interface import (
    AccountRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.security.interface import SessionTokenProviderPort
from backend.domain.account.user_state import UserState
from backend.shared.errors.errors import AuthenticationRequiredError


class AuthenticateSessionUseCase:
    """ログインセッショントークンを検証し、認証済みユーザを返す。"""

    def __init__(
        self,
        repository: AccountRepositoryPort,
        token_provider: SessionTokenProviderPort,
        clock: ClockPort,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._token_provider = token_provider
        self._clock = clock
        self._transaction_manager = transaction_manager_or_noop(transaction_manager)

    def execute(
        self, session_token: str | None, trace_id: str = ""
    ) -> AuthenticatedUser:
        """Cookieトークンから現在ユーザを返す。"""
        _ = trace_id
        if session_token is None or session_token == "":
            raise AuthenticationRequiredError()
        token_hash = self._token_provider.hash_token(session_token)
        with self._transaction_manager.transaction():
            session = self._repository.find_session_by_token_hash(token_hash)
            if session is None:
                raise AuthenticationRequiredError()
            if (
                session.expires_at <= self._clock.now()
                or session.user_state is UserState.DELETING
            ):
                self._repository.delete_session_by_token_hash(token_hash)
                session = None
        if session is None:
            raise AuthenticationRequiredError()
        return AuthenticatedUser(user_id=session.user_id, user_name=session.user_name)

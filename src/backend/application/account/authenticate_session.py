from __future__ import annotations

from dataclasses import dataclass

from backend.application.account.dto import AuthenticatedUserResult
from backend.application.account.errors import AuthenticationRequiredError
from backend.application.account.interfaces import AccountRepositoryLike
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import ClockPort
from backend.application.ports.security.interface import SessionTokenProviderPort
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class AuthenticateSessionCommand:
    """ログインセッション認証要求。"""

    session_token: str | None
    trace_id: TraceId


class AuthenticateSessionUseCase:
    """Cookieセッションを照合し、認証済みユーザを返す。"""

    def __init__(
        self,
        *,
        repository: AccountRepositoryLike,
        transaction_manager: TransactionManagerPort,
        session_token_provider: SessionTokenProviderPort,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._session_token_provider = session_token_provider
        self._clock = clock

    def execute(
        self,
        command: AuthenticateSessionCommand,
    ) -> AuthenticatedUserResult:
        """セッションの有効期限とユーザ状態を検証する。"""

        if command.session_token is None:
            raise AuthenticationRequiredError()

        token_hash = self._session_token_provider.hash_token(command.session_token)
        session = self._repository.find_session_by_token_hash(token_hash)
        if session is None:
            raise AuthenticationRequiredError()

        should_delete = (
            session.expires_at <= self._clock.now_utc()
            or session.user_state != "active"
        )
        if should_delete:
            with self._transaction_manager:
                self._repository.delete_session_by_token_hash(token_hash)
            raise AuthenticationRequiredError()

        return AuthenticatedUserResult(
            user_id=session.user_id,
            user_name=session.user_name,
        )

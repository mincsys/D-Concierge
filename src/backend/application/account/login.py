from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from backend.application.account.dto import (
    AuthenticatedUserResult,
    SessionIssueResult,
)
from backend.application.account.errors import FieldValidationError
from backend.application.account.interfaces import AccountRepositoryLike
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import ClockPort
from backend.application.ports.security.interface import (
    PasswordHasherPort,
    SessionTokenProviderPort,
)
from backend.shared.tracing.trace_id import TraceId

SESSION_LIFETIME_DAYS = 400


@dataclass(frozen=True, slots=True)
class LoginCommand:
    """ログイン要求。"""

    user_id: str
    password: str
    existing_session_token: str | None
    trace_id: TraceId


class LoginUseCase:
    """ログインを調停する。"""

    def __init__(
        self,
        *,
        repository: AccountRepositoryLike,
        transaction_manager: TransactionManagerPort,
        password_hasher: PasswordHasherPort,
        session_token_provider: SessionTokenProviderPort,
        clock: ClockPort,
        session_lifetime_days: int = SESSION_LIFETIME_DAYS,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._password_hasher = password_hasher
        self._session_token_provider = session_token_provider
        self._clock = clock
        self._session_lifetime_days = session_lifetime_days

    def execute(self, command: LoginCommand) -> SessionIssueResult:
        """認証に成功したユーザのログインセッションを発行する。"""

        user = self._repository.get_user_for_login(command.user_id)
        if user is None or user.user_state != "active":
            raise FieldValidationError(
                {"user_id": "ユーザIDまたはアカウント状態を確認してください。"}
            )
        if not self._password_hasher.verify_password(
            command.password,
            user.password_hash,
        ):
            raise FieldValidationError({"password": "パスワードを確認してください。"})

        now = self._clock.now_utc()
        session_token = self._session_token_provider.issue_token()
        token_hash = self._session_token_provider.hash_token(session_token)
        expires_at = now + timedelta(days=self._session_lifetime_days)
        existing_token_hash = (
            self._session_token_provider.hash_token(command.existing_session_token)
            if command.existing_session_token is not None
            else None
        )

        with self._transaction_manager:
            if existing_token_hash is not None:
                self._repository.delete_session_by_token_hash(existing_token_hash)
            self._repository.create_login_session(
                token_hash,
                user.user_id,
                expires_at,
                now,
            )

        return SessionIssueResult(
            user=AuthenticatedUserResult(
                user_id=user.user_id,
                user_name=user.user_name,
            ),
            session_token=session_token,
            expires_at=expires_at,
        )

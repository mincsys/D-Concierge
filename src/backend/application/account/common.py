from datetime import datetime, timedelta
from typing import Protocol

from backend.application.ports.database.dto import IssuedLoginSession
from backend.application.ports.database.interface import (
    LoginSessionRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.security.interface import (
    SessionTokenProviderPort,
)
from backend.application.transactions import NoopTransactionManager
from backend.domain.account.user_state import UserState
from backend.shared.errors.errors import FieldValidationError
from backend.shared.user_messages import (
    PASSWORD_CONFIRMATION_MISMATCH_MESSAGE,
)

SESSION_MAX_AGE_DAYS = 400


class ClockPort(Protocol):
    """現在時刻取得境界。"""

    def now(self) -> datetime:
        """現在時刻を返す。"""


def raise_if_field_errors(field_errors: dict[str, str]) -> None:
    """項目別エラーがあれば例外化する。"""
    if field_errors:
        raise FieldValidationError(field_errors)


def confirmation_error(password: str, confirmation: str) -> str | None:
    """確認用パスワードの不一致メッセージを返す。"""
    if password != confirmation:
        return PASSWORD_CONFIRMATION_MISMATCH_MESSAGE
    return None


class LoginSessionIssuer:
    """ログインセッション発行の共通処理。"""

    def __init__(
        self,
        token_provider: SessionTokenProviderPort,
        clock: ClockPort,
    ) -> None:
        self._token_provider = token_provider
        self._clock = clock

    def issue(
        self,
        repository: LoginSessionRepositoryPort,
        user_id: str,
        user_name: str,
        existing_session_token: str | None,
    ) -> IssuedLoginSession:
        """新しいセッションを保存し、Cookie設定用トークンを返す。"""
        now = self._clock.now()
        token = self._token_provider.issue_token()
        expires_at = now + timedelta(days=SESSION_MAX_AGE_DAYS)
        if existing_session_token is not None:
            repository.delete_session_by_token_hash(
                self._token_provider.hash_token(existing_session_token)
            )
        repository.create_login_session(
            self._token_provider.hash_token(token),
            user_id,
            expires_at,
            now,
        )
        from backend.application.ports.database.dto import AuthenticatedUser

        return IssuedLoginSession(
            user=AuthenticatedUser(user_id=user_id, user_name=user_name),
            session_token=token,
            expires_at=expires_at,
        )


def is_active_user_state(user_state: UserState) -> bool:
    """通常ユーザ状態であればTrue。"""
    return user_state is UserState.ACTIVE


def transaction_manager_or_noop(
    transaction_manager: TransactionManagerPort | None,
) -> TransactionManagerPort:
    """未指定時はNoopトランザクションを返す。"""
    return (
        transaction_manager
        if transaction_manager is not None
        else NoopTransactionManager()
    )

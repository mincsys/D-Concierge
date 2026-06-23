from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from backend.application.account.dto import (
    AuthenticatedUserResult,
    SessionIssueResult,
)
from backend.application.account.errors import FieldValidationError
from backend.application.account.interfaces import AccountRepositoryLike
from backend.application.account.validation import (
    validate_password,
    validate_user_id,
    validate_user_name,
)
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import ClockPort
from backend.application.ports.security.interface import (
    PasswordHasherPort,
    SessionTokenProviderPort,
)
from backend.shared.tracing.trace_id import TraceId

SESSION_LIFETIME_DAYS = 400


@dataclass(frozen=True, slots=True)
class RegisterAccountCommand:
    """アカウント登録要求。"""

    user_id: str
    user_name: str
    password: str
    password_confirmation: str
    existing_session_token: str | None
    trace_id: TraceId


class RegisterAccountUseCase:
    """アカウント登録を調停する。"""

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

    def execute(self, command: RegisterAccountCommand) -> SessionIssueResult:
        """登録入力を検証し、ユーザとログインセッションを作成する。"""

        field_errors = _validate_register_input(command)
        if self._repository.get_user_for_login(command.user_id) is not None:
            field_errors["user_id"] = "このユーザIDは既に使用されています。"
        if field_errors:
            raise FieldValidationError(field_errors)

        now = self._clock.now_utc()
        password_hash = self._password_hasher.hash_password(command.password)
        session_token = self._session_token_provider.issue_token()
        token_hash = self._session_token_provider.hash_token(session_token)
        expires_at = now + timedelta(days=self._session_lifetime_days)
        existing_token_hash = (
            self._session_token_provider.hash_token(command.existing_session_token)
            if command.existing_session_token is not None
            else None
        )

        with self._transaction_manager:
            user = self._repository.create_user(
                command.user_id,
                command.user_name,
                password_hash,
                now,
            )
            if existing_token_hash is not None:
                self._repository.delete_session_by_token_hash(existing_token_hash)
            self._repository.create_login_session(
                token_hash,
                command.user_id,
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


def _validate_register_input(
    command: RegisterAccountCommand,
) -> dict[str, str]:
    field_errors: dict[str, str] = {}
    user_id_error = validate_user_id(command.user_id)
    if user_id_error is not None:
        field_errors["user_id"] = user_id_error
    user_name_error = validate_user_name(command.user_name)
    if user_name_error is not None:
        field_errors["user_name"] = user_name_error
    password_error = validate_password("パスワード", command.password)
    if password_error is not None:
        field_errors["password"] = password_error
    if command.password != command.password_confirmation:
        field_errors["password_confirmation"] = "パスワード確認が一致しません。"
    return field_errors

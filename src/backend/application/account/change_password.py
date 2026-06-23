from __future__ import annotations

from dataclasses import dataclass

from backend.application.account.errors import FieldValidationError
from backend.application.account.interfaces import AccountRepositoryLike
from backend.application.account.validation import validate_password
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import ClockPort
from backend.application.ports.security.interface import PasswordHasherPort
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class ChangePasswordCommand:
    """パスワード変更要求。"""

    authenticated_user_id: str
    current_password: str
    new_password: str
    new_password_confirmation: str
    trace_id: TraceId


class ChangePasswordUseCase:
    """認証済みユーザのパスワードを変更する。"""

    def __init__(
        self,
        *,
        repository: AccountRepositoryLike,
        transaction_manager: TransactionManagerPort,
        password_hasher: PasswordHasherPort,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._password_hasher = password_hasher
        self._clock = clock

    def execute(self, command: ChangePasswordCommand) -> None:
        """現在パスワードを確認し、新パスワードハッシュだけを保存する。"""

        field_errors = _validate_change_password_input(command)
        if field_errors:
            raise FieldValidationError(field_errors)

        user = self._repository.get_user_for_login(command.authenticated_user_id)
        if user is None or user.user_state != "active":
            raise FieldValidationError(
                {"current_password": "現在のパスワードを確認してください。"}
            )
        if not self._password_hasher.verify_password(
            command.current_password,
            user.password_hash,
        ):
            raise FieldValidationError(
                {"current_password": "現在のパスワードを確認してください。"}
            )

        password_hash = self._password_hasher.hash_password(command.new_password)
        with self._transaction_manager:
            self._repository.update_password_hash(
                command.authenticated_user_id,
                password_hash,
                self._clock.now_utc(),
            )


def _validate_change_password_input(
    command: ChangePasswordCommand,
) -> dict[str, str]:
    field_errors: dict[str, str] = {}
    new_password_error = validate_password("新しいパスワード", command.new_password)
    if new_password_error is not None:
        field_errors["new_password"] = new_password_error
    if command.new_password != command.new_password_confirmation:
        field_errors["new_password_confirmation"] = (
            "新しいパスワード確認が一致しません。"
        )
    return field_errors

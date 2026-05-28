from datetime import UTC, datetime

from backend.application.account.common import transaction_manager_or_noop
from backend.application.ports.database.interface import (
    AccountRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import ClockPort
from backend.application.ports.security.interface import PasswordHasherPort
from backend.domain.account.password_policy import PasswordPolicy
from backend.shared.errors.errors import FieldValidationError
from backend.shared.user_messages import (
    CURRENT_PASSWORD_MISMATCH_MESSAGE,
    PASSWORD_CONFIRMATION_MISMATCH_MESSAGE,
)


class ChangePasswordUseCase:
    """パスワード変更を調停する。"""

    def __init__(
        self,
        repository: AccountRepositoryPort,
        password_hasher: PasswordHasherPort,
        clock: ClockPort | None = None,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._clock = clock
        self._transaction_manager = transaction_manager_or_noop(transaction_manager)

    def execute(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        new_password_confirmation: str,
        trace_id: str = "",
    ) -> None:
        """現在パスワードを検証し、新しいパスワードハッシュを保存する。"""
        _ = trace_id
        with self._transaction_manager.transaction():
            user = self._repository.get_user_for_login(user_id)
            field_errors: dict[str, str] = {}
            if user is None or not self._password_hasher.verify_password(
                current_password, user.password_hash
            ):
                field_errors["current_password"] = CURRENT_PASSWORD_MISMATCH_MESSAGE
            password_errors = PasswordPolicy.validate(new_password)
            if password_errors:
                field_errors["new_password"] = password_errors[0]
            if new_password != new_password_confirmation:
                field_errors["new_password_confirmation"] = (
                    PASSWORD_CONFIRMATION_MISMATCH_MESSAGE
                )
            if field_errors:
                raise FieldValidationError(field_errors)
            now = self._clock.now() if self._clock is not None else datetime.now(UTC)
            self._repository.update_password_hash(
                user_id, self._password_hasher.hash_password(new_password), now
            )

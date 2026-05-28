from datetime import UTC, datetime

from backend.application.account.common import transaction_manager_or_noop
from backend.application.ports.database.dto import AuthenticatedUser
from backend.application.ports.database.interface import (
    AccountRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import ClockPort
from backend.domain.account.user_name_policy import UserNamePolicy
from backend.shared.errors.errors import FieldValidationError


class ChangeUserNameUseCase:
    """ユーザ名変更を調停する。"""

    def __init__(
        self,
        repository: AccountRepositoryPort,
        clock: ClockPort | None = None,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._transaction_manager = transaction_manager_or_noop(transaction_manager)

    def execute(
        self, user_id: str, user_name: str, trace_id: str = ""
    ) -> AuthenticatedUser:
        """ユーザ名を更新する。"""
        _ = trace_id
        errors = UserNamePolicy.validate(user_name)
        if errors:
            raise FieldValidationError({"user_name": errors[0]})
        now = self._clock.now() if self._clock is not None else datetime.now(UTC)
        with self._transaction_manager.transaction():
            user = self._repository.update_user_name(user_id, user_name, now)
        return AuthenticatedUser(user_id=user.user_id, user_name=user.user_name)

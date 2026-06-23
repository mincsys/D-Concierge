from __future__ import annotations

from dataclasses import dataclass

from backend.application.account.dto import AuthenticatedUserResult
from backend.application.account.errors import FieldValidationError
from backend.application.account.interfaces import AccountRepositoryLike
from backend.application.account.validation import validate_user_name
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import ClockPort
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class ChangeUserNameCommand:
    """ユーザ名変更要求。"""

    authenticated_user_id: str
    user_name: str
    trace_id: TraceId


class ChangeUserNameUseCase:
    """認証済みユーザの表示名を変更する。"""

    def __init__(
        self,
        *,
        repository: AccountRepositoryLike,
        transaction_manager: TransactionManagerPort,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._clock = clock

    def execute(self, command: ChangeUserNameCommand) -> AuthenticatedUserResult:
        """ユーザ名を検証してactiveユーザだけを更新する。"""

        user_name_error = validate_user_name(command.user_name)
        if user_name_error is not None:
            raise FieldValidationError({"user_name": user_name_error})

        with self._transaction_manager:
            user = self._repository.update_user_name(
                command.authenticated_user_id,
                command.user_name,
                self._clock.now_utc(),
            )
        if user is None:
            raise FieldValidationError({"user_name": "ユーザ名を変更できません。"})

        return AuthenticatedUserResult(
            user_id=user.user_id,
            user_name=user.user_name,
        )

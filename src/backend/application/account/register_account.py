from backend.application.account.common import (
    ClockPort,
    LoginSessionIssuer,
    confirmation_error,
    raise_if_field_errors,
    transaction_manager_or_noop,
)
from backend.application.ports.database.dto import IssuedLoginSession
from backend.application.ports.database.interface import (
    AccountRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.security.interface import (
    PasswordHasherPort,
    SessionTokenProviderPort,
)
from backend.domain.account.password_policy import PasswordPolicy
from backend.domain.account.user_id_policy import UserIdPolicy
from backend.domain.account.user_name_policy import UserNamePolicy
from backend.shared.user_messages import USER_ID_DUPLICATED_MESSAGE


class RegisterAccountUseCase:
    """アカウント登録とログインセッション発行を調停する。"""

    def __init__(
        self,
        repository: AccountRepositoryPort,
        password_hasher: PasswordHasherPort,
        token_provider: SessionTokenProviderPort,
        clock: ClockPort,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._issuer = LoginSessionIssuer(token_provider, clock)
        self._clock = clock
        self._transaction_manager = transaction_manager_or_noop(transaction_manager)

    def execute(
        self,
        user_id: str,
        user_name: str,
        password: str,
        password_confirmation: str,
        existing_session_token: str | None,
        trace_id: str = "",
    ) -> IssuedLoginSession:
        """ユーザを作成し、新規ログインセッションを発行する。"""
        _ = trace_id
        with self._transaction_manager.transaction():
            field_errors = _registration_field_errors(
                self._repository, user_id, user_name, password, password_confirmation
            )
            raise_if_field_errors(field_errors)
            password_hash = self._password_hasher.hash_password(password)
            self._repository.create_user(
                user_id, user_name, password_hash, self._clock.now()
            )
            return self._issuer.issue(
                self._repository, user_id, user_name, existing_session_token
            )


def _registration_field_errors(
    repository: AccountRepositoryPort,
    user_id: str,
    user_name: str,
    password: str,
    password_confirmation: str,
) -> dict[str, str]:
    field_errors: dict[str, str] = {}
    user_id_errors = UserIdPolicy.validate(user_id)
    if user_id_errors:
        field_errors["user_id"] = user_id_errors[0]
    elif repository.get_user_for_login(user_id) is not None:
        field_errors["user_id"] = USER_ID_DUPLICATED_MESSAGE
    user_name_errors = UserNamePolicy.validate(user_name)
    if user_name_errors:
        field_errors["user_name"] = user_name_errors[0]
    password_errors = PasswordPolicy.validate(password)
    if password_errors:
        field_errors["password"] = password_errors[0]
    confirmation = confirmation_error(password, password_confirmation)
    if confirmation is not None:
        field_errors["password_confirmation"] = confirmation
    return field_errors

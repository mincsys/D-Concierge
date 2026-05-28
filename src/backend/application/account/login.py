from backend.application.account.common import (
    ClockPort,
    LoginSessionIssuer,
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
from backend.domain.account.user_state import UserState
from backend.shared.errors.errors import FieldValidationError
from backend.shared.user_messages import (
    ACCOUNT_UNAVAILABLE_MESSAGE,
    LOGIN_PASSWORD_MISMATCH_MESSAGE,
    LOGIN_USER_NOT_FOUND_MESSAGE,
)


class LoginUseCase:
    """ユーザIDとパスワードを検証し、ログインセッションを発行する。"""

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
        self._transaction_manager = transaction_manager_or_noop(transaction_manager)

    def execute(
        self,
        user_id: str,
        password: str,
        existing_session_token: str | None,
        trace_id: str = "",
    ) -> IssuedLoginSession:
        """ログイン認証を行い、新規ログインセッションを発行する。"""
        _ = trace_id
        with self._transaction_manager.transaction():
            user = self._repository.get_user_for_login(user_id)
            if user is None:
                raise FieldValidationError({"user_id": LOGIN_USER_NOT_FOUND_MESSAGE})
            if user.user_state is UserState.DELETING:
                raise FieldValidationError({"user_id": ACCOUNT_UNAVAILABLE_MESSAGE})
            if not self._password_hasher.verify_password(password, user.password_hash):
                raise FieldValidationError(
                    {"password": LOGIN_PASSWORD_MISMATCH_MESSAGE}
                )
            return self._issuer.issue(
                self._repository, user.user_id, user.user_name, existing_session_token
            )

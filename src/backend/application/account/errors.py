from __future__ import annotations

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.user_messages import AUTHENTICATION_REQUIRED, INPUT_ERROR


class FieldValidationError(AppError):
    """入力項目ごとの検証エラー。"""

    def __init__(self, field_errors: dict[str, str]) -> None:
        self.field_errors = field_errors
        super().__init__(
            error_type=ErrorType.INPUT,
            trace=False,
            diagnostic_message=INPUT_ERROR,
        )


class AuthenticationRequiredError(AppError):
    """未ログインまたは無効セッションを表すエラー。"""

    def __init__(self) -> None:
        super().__init__(
            error_type=ErrorType.FORBIDDEN,
            trace=False,
            diagnostic_message=AUTHENTICATION_REQUIRED,
        )

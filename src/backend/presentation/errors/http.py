from backend.presentation.schemas.api import ErrorResponseSchema
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import (
    ActiveRunConflictError,
    AppError,
    ArtifactAlreadySavedError,
    ArtifactNotDisplayableError,
    ArtifactNotFoundError,
    AuthenticationRequiredError,
    CancelNotAllowedError,
    ChatDeletingError,
    ChatNotFoundError,
    ChatRunNotFoundError,
    FieldValidationError,
    FileNotDisplayableError,
    ProcessCanceledConflictError,
    ReferenceNotDisplayableError,
    ReferenceNotFoundError,
    RunNotFoundError,
    UserInstructionRequiredError,
)
from backend.shared.user_messages import (
    ACTIVE_RUN_CONFLICT_MESSAGE,
    ARTIFACT_ALREADY_SAVED_MESSAGE,
    ARTIFACT_NOT_DISPLAYABLE_MESSAGE,
    ARTIFACT_NOT_FOUND_MESSAGE,
    CANCEL_NOT_ALLOWED_MESSAGE,
    CHAT_DELETING_MESSAGE,
    CHAT_NOT_FOUND_MESSAGE,
    CHAT_RUN_NOT_FOUND_MESSAGE,
    CONFIGURATION_FAILURE_MESSAGE,
    FILE_NOT_DISPLAYABLE_MESSAGE,
    LOGIN_REQUIRED_MESSAGE,
    PROCESS_CANCELED_CONFLICT_MESSAGE,
    REFERENCE_NOT_DISPLAYABLE_MESSAGE,
    REFERENCE_NOT_FOUND_MESSAGE,
    REQUEST_VALIDATION_FAILURE_MESSAGE,
    RUN_NOT_FOUND_MESSAGE,
    UNEXPECTED_FAILURE_MESSAGE,
    USER_INSTRUCTION_REQUIRED_MESSAGE,
)


def error_response_payload(
    error_type: ErrorType,
    user_message: str,
    field_errors: dict[str, str] | None = None,
) -> ErrorResponseSchema:
    """公開APIエラーpayloadを生成する。"""
    return ErrorResponseSchema(
        error=error_type.value,
        message=user_message,
        field_errors=field_errors,
    )


def user_message_for_error(error: AppError) -> str:
    """AppErrorを利用者向けメッセージへ変換する。"""
    match error:
        case UserInstructionRequiredError():
            return USER_INSTRUCTION_REQUIRED_MESSAGE
        case ChatNotFoundError():
            return CHAT_NOT_FOUND_MESSAGE
        case ChatDeletingError():
            return CHAT_DELETING_MESSAGE
        case RunNotFoundError():
            return RUN_NOT_FOUND_MESSAGE
        case ChatRunNotFoundError():
            return CHAT_RUN_NOT_FOUND_MESSAGE
        case ReferenceNotFoundError():
            return REFERENCE_NOT_FOUND_MESSAGE
        case ArtifactNotFoundError():
            return ARTIFACT_NOT_FOUND_MESSAGE
        case ReferenceNotDisplayableError():
            return REFERENCE_NOT_DISPLAYABLE_MESSAGE
        case ArtifactNotDisplayableError():
            return ARTIFACT_NOT_DISPLAYABLE_MESSAGE
        case FileNotDisplayableError():
            return FILE_NOT_DISPLAYABLE_MESSAGE
        case ActiveRunConflictError():
            return ACTIVE_RUN_CONFLICT_MESSAGE
        case CancelNotAllowedError():
            return CANCEL_NOT_ALLOWED_MESSAGE
        case ProcessCanceledConflictError():
            return PROCESS_CANCELED_CONFLICT_MESSAGE
        case ArtifactAlreadySavedError():
            return ARTIFACT_ALREADY_SAVED_MESSAGE
        case AuthenticationRequiredError():
            return LOGIN_REQUIRED_MESSAGE
        case FieldValidationError():
            return REQUEST_VALIDATION_FAILURE_MESSAGE
        case _:
            if error.error_type is ErrorType.CONFIGURATION:
                return CONFIGURATION_FAILURE_MESSAGE
            return UNEXPECTED_FAILURE_MESSAGE


def status_code(error_type: ErrorType) -> int:
    """AppError分類をHTTPステータスへ変換する。"""
    match error_type:
        case ErrorType.INPUT | ErrorType.CONFIGURATION:
            return 400
        case ErrorType.NOT_FOUND:
            return 404
        case ErrorType.CONFLICT:
            return 409
        case ErrorType.UNAUTHORIZED:
            return 401
        case ErrorType.FORBIDDEN:
            return 403
        case ErrorType.SYSTEM:
            return 500

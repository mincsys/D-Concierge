from backend.presentation.schemas.api import ErrorResponseSchema
from backend.shared.errors import AppError, ErrorClass


def error_response_payload(error: AppError) -> ErrorResponseSchema:
    """AppErrorを公開APIエラーpayloadへ変換する。"""
    return ErrorResponseSchema(
        error=error.error_class.value,
        message=error.user_message,
    )


def status_code(error_class: ErrorClass) -> int:
    """AppError分類をHTTPステータスへ変換する。"""
    match error_class:
        case ErrorClass.INPUT | ErrorClass.CONFIGURATION:
            return 400
        case ErrorClass.NOT_FOUND:
            return 404
        case ErrorClass.CONFLICT:
            return 409
        case ErrorClass.FORBIDDEN:
            return 403
        case ErrorClass.SYSTEM:
            return 500

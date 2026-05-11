from backend.presentation.errors.http import error_response_payload, status_code
from backend.shared.error_class import ErrorClass
from backend.shared.errors import AppError


def test_app_error_handler_response() -> None:
    """観点：presentation errors。確認：AppErrorをHTTP状態と公開payloadへ変換する。"""
    error = AppError(ErrorClass.NOT_FOUND, "対象がありません。")

    payload = error_response_payload(error)

    assert status_code(error.error_class) == 404
    assert payload.error == "not_found"
    assert payload.message == "対象がありません。"

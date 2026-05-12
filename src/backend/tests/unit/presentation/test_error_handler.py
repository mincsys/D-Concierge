from backend.presentation.errors.http import (
    error_response_payload,
    status_code,
    user_message_for_error,
)
from backend.shared.errors.errors import ReferenceNotFoundError


def test_app_error_handler_response() -> None:
    """観点：presentation errors。確認：AppErrorをHTTP状態と公開payloadへ変換する。"""
    error = ReferenceNotFoundError()

    payload = error_response_payload(error.error_type, user_message_for_error(error))

    assert status_code(error.error_type) == 404
    assert payload.error == "not_found"
    assert payload.message == "対象の参照元が見つかりません。"

import pytest

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


def test_app_error_keeps_internal_diagnostic_contract() -> None:
    """観点：共通エラー。確認：AppErrorは診断情報だけを保持する。"""
    error = AppError(
        ErrorType.SYSTEM,
        trace=True,
        diagnostic_message="DB接続に失敗しました。",
    )

    assert error.error_type is ErrorType.SYSTEM
    assert error.trace is True
    assert error.diagnostic_message == "DB接続に失敗しました。"
    assert error.cause is None
    assert not hasattr(error, "user_message")


def test_app_error_rejects_invalid_diagnostic_usage() -> None:
    """観点：共通エラー。確認：trace有無と診断メッセージの契約を強制する。"""
    with pytest.raises(ValueError):
        AppError(ErrorType.SYSTEM, trace=True)

    with pytest.raises(ValueError):
        AppError(ErrorType.INPUT, diagnostic_message="画面向け文言")

import pytest

from backend.domain.account.password_policy import PasswordPolicy
from backend.domain.account.user_id_policy import UserIdPolicy
from backend.domain.account.user_name_policy import UserNamePolicy
from backend.shared.user_messages import USER_ID_FORMAT_MESSAGE


@pytest.mark.parametrize(
    "value",
    ["a", "abc-123_def", "A" * 30, "0_1-2"],
)
def test_user_id_policy_accepts_allowed_values(value: str) -> None:
    """観点：U-ACC-001。確認：設計どおりのユーザIDを許可する。"""
    assert UserIdPolicy.validate(value) == []


@pytest.mark.parametrize(
    "value",
    ["", "-abc", "abc_", "abc.def", "a" * 31, "あいう"],
)
def test_user_id_policy_rejects_invalid_values(value: str) -> None:
    """観点：U-ACC-001。確認：形式外のユーザIDを拒否する。"""
    assert UserIdPolicy.validate(value) == [USER_ID_FORMAT_MESSAGE]


def test_user_name_policy_accepts_any_non_empty_30_chars() -> None:
    """観点：U-ACC-002。確認：ユーザ名は文字種を制限しない。"""
    assert UserNamePolicy.validate("デモ_ユーザ-01") == []
    assert UserNamePolicy.validate("あ" * 30) == []


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "ユーザ名を入力してください。"),
        ("a" * 31, "ユーザ名は30文字以内で入力してください。"),
    ],
)
def test_user_name_policy_rejects_empty_and_too_long(value: str, message: str) -> None:
    """観点：U-ACC-002。確認：空文字と31文字以上を拒否する。"""
    assert UserNamePolicy.validate(value) == [message]


@pytest.mark.parametrize("value", ["abc12", "A1-_$%", "x" * 30])
def test_password_policy_accepts_visible_ascii_between_5_and_30(value: str) -> None:
    """観点：U-ACC-003。確認：5から30文字の半角英数字・記号を許可する。"""
    assert PasswordPolicy.validate(value) == []


@pytest.mark.parametrize("value", ["", "abcd", "a" * 31, "abc12あ", "abc 12"])
def test_password_policy_rejects_invalid_values(value: str) -> None:
    """観点：U-ACC-003。確認：長さ外、全角、空白を拒否する。"""
    assert PasswordPolicy.validate(value) == [
        "パスワードは5文字以上30文字以内の半角英数字と記号で入力してください。"
    ]

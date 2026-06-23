from __future__ import annotations

import re

USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,28}[A-Za-z0-9])?$")
PASSWORD_PATTERN = re.compile(r"^[!-~]+$")
PASSWORD_MIN_LENGTH = 5
PASSWORD_MAX_LENGTH = 30
USER_NAME_MAX_LENGTH = 30


def validate_user_id(user_id: str) -> str | None:
    """ユーザIDの入力エラー文言を返す。"""

    if not USER_ID_PATTERN.fullmatch(user_id):
        return "ユーザIDは1文字以上30文字以内の半角英数字、_、-で入力してください。"
    return None


def validate_user_name(user_name: str) -> str | None:
    """ユーザ名の入力エラー文言を返す。"""

    if len(user_name) == 0 or len(user_name) > USER_NAME_MAX_LENGTH:
        return "ユーザ名は1文字以上30文字以内で入力してください。"
    return None


def validate_password(field_name: str, password: str) -> str | None:
    """パスワードの入力エラー文言を返す。"""

    if len(password) < PASSWORD_MIN_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        return f"{field_name}は5文字以上30文字以内で入力してください。"
    if not PASSWORD_PATTERN.fullmatch(password):
        return f"{field_name}は半角の英字、数字、記号で入力してください。"
    return None

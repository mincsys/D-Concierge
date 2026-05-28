import re

from backend.shared.user_messages import USER_ID_FORMAT_MESSAGE

_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,28}[A-Za-z0-9])?$")


class UserIdPolicy:
    """ユーザID入力規則。"""

    @staticmethod
    def validate(value: str) -> list[str]:
        """ユーザIDの入力エラーを返す。"""
        if not _USER_ID_PATTERN.fullmatch(value):
            return [USER_ID_FORMAT_MESSAGE]
        return []

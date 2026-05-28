import re

from backend.shared.user_messages import PASSWORD_FORMAT_MESSAGE

_PASSWORD_PATTERN = re.compile(r"^[!-~]{5,30}$")


class PasswordPolicy:
    """パスワード入力規則。"""

    @staticmethod
    def validate(value: str) -> list[str]:
        """パスワードの入力エラーを返す。"""
        if not _PASSWORD_PATTERN.fullmatch(value):
            return [PASSWORD_FORMAT_MESSAGE]
        return []

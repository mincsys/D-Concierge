from backend.shared.user_messages import (
    USER_NAME_LENGTH_MESSAGE,
    USER_NAME_REQUIRED_MESSAGE,
)


class UserNamePolicy:
    """ユーザ名入力規則。"""

    @staticmethod
    def validate(value: str) -> list[str]:
        """ユーザ名の入力エラーを返す。"""
        if value == "":
            return [USER_NAME_REQUIRED_MESSAGE]
        if len(value) > 30:
            return [USER_NAME_LENGTH_MESSAGE]
        return []

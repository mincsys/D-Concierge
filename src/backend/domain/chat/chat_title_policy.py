from backend.domain.chat.user_instruction import UserInstruction


class ChatTitlePolicy:
    """ユーザ指示本文から履歴タイトルを生成する方針。"""

    DEFAULT_TITLE = "新しいチャット"
    MAX_LENGTH = 50

    @classmethod
    def make_title(cls, instruction: UserInstruction) -> str:
        """ユーザ指示からチャットタイトルを生成する。"""
        return cls.make_title_from_text(instruction.body)

    @classmethod
    def make_title_from_text(cls, text: str) -> str:
        """任意本文からチャットタイトルを生成する。"""
        title = " ".join(text.split())
        if title == "":
            return cls.DEFAULT_TITLE
        return title[: cls.MAX_LENGTH]

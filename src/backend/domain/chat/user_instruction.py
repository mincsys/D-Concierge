from dataclasses import dataclass

from backend.shared.user_messages import USER_INSTRUCTION_REQUIRED_MESSAGE


class InvalidUserInstructionError(ValueError):
    """ユーザ指示本文が成立しないことを示すドメインエラー。"""


@dataclass(frozen=True, slots=True)
class UserInstruction:
    """1回分のユーザ指示本文。"""

    body: str

    def __init__(self, body: str) -> None:
        normalized = body.strip()
        if normalized == "":
            raise InvalidUserInstructionError(USER_INSTRUCTION_REQUIRED_MESSAGE)
        object.__setattr__(self, "body", normalized)

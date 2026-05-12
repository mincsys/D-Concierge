from dataclasses import dataclass


class InvalidUserInstructionError(ValueError):
    """ユーザ指示本文が成立しないことを示すドメインエラー。"""


@dataclass(frozen=True, slots=True)
class UserInstruction:
    """1回分のユーザ指示本文。"""

    body: str

    def __init__(self, body: str) -> None:
        normalized = body.strip()
        if normalized == "":
            raise InvalidUserInstructionError("ユーザ指示本文が空です。")
        object.__setattr__(self, "body", normalized)

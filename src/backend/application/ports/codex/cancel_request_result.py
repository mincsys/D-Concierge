from enum import Enum


class CancelRequestResult(Enum):
    """Codexキャンセル要求結果。"""

    SENT = "sent"
    ALREADY_EXITED = "already_exited"
    NOT_REGISTERED = "not_registered"

from enum import Enum


class ChatState(Enum):
    """チャット単位のライフサイクル状態。"""

    ACTIVE = "active"
    DELETING = "deleting"

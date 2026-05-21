from enum import Enum


class ChatState(Enum):
    """チャット単位のライフサイクル状態。"""

    ACTIVE = "有効"
    DELETING = "削除中"

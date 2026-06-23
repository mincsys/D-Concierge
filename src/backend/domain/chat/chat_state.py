from __future__ import annotations

from enum import Enum


class ChatState(Enum):
    """チャットのライフサイクル状態。"""

    ACTIVE = "active"
    DELETING = "deleting"

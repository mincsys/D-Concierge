from __future__ import annotations

from enum import Enum


class UserState(Enum):
    """ユーザの利用状態。"""

    ACTIVE = "active"
    DELETING = "deleting"

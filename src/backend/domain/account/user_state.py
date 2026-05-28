from enum import Enum


class UserState(Enum):
    """ユーザアカウントの状態。"""

    ACTIVE = "active"
    DELETING = "deleting"

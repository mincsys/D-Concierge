from enum import Enum


class UserState(Enum):
    """ユーザアカウントの状態。"""

    ACTIVE = "通常"
    DELETING = "削除中"

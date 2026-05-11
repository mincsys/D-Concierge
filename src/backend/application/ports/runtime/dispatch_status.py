from enum import Enum


class DispatchStatus(Enum):
    """run登録結果の状態。"""

    REGISTERED = "registered"
    ALREADY_REGISTERED = "already_registered"
    FAILED = "failed"

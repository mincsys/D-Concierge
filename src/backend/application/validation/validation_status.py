from enum import Enum


class ValidationStatus(Enum):
    """回答検証UseCaseの判定状態。"""

    ACCEPTED = "accepted"
    REGENERATE = "regenerate"
    FAILED = "failed"

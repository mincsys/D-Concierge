from enum import Enum


class ValidationStatus(Enum):
    """回答検証UseCaseの判定状態。"""

    ACCEPTED = "採用可能"
    REGENERATE = "再生成指示"
    FAILED = "失敗"

from enum import Enum


class CodexOutputKind(Enum):
    """Codex出力payloadの種別。"""

    PROGRESS = "progress"
    FINAL = "final"

from __future__ import annotations

from enum import Enum


class RunState(Enum):
    """チャット実行処理の状態。"""

    ACCEPTED = "accepted"
    RUNNING = "running"
    VALIDATING = "validating"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELED = "canceled"
    COMPLETED = "completed"
    ERROR = "error"
    TIMED_OUT = "timed_out"

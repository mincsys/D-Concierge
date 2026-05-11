from enum import Enum


class CodexEventKind(Enum):
    """Codex JSONLイベント種別。"""

    THREAD_STARTED = "thread_started"
    TURN_STARTED = "turn_started"
    ITEM_STARTED = "item_started"
    AGENT_MESSAGE = "agent_message"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    ERROR = "error"
    UNKNOWN = "unknown"

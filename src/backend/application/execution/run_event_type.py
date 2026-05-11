from enum import Enum


class RunEventType(Enum):
    """run ID単位で発行するイベント種別。"""

    STATE = "state"
    MESSAGE = "message"
    ANSWER = "answer"
    ERROR = "error"
    CANCELED = "canceled"

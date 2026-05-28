from enum import Enum


class ErrorType(Enum):
    """アプリケーション全体で扱うエラー分類。"""

    INPUT = "input"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    CONFIGURATION = "configuration"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    SYSTEM = "system"

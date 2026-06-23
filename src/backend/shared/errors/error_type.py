from __future__ import annotations

from enum import Enum


class ErrorType(Enum):
    """アプリケーション横断のエラー分類。"""

    INPUT = "input"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    CONFIGURATION = "configuration"
    FORBIDDEN = "forbidden"
    SYSTEM = "system"

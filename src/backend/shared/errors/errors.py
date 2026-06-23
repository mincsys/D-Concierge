from __future__ import annotations

from dataclasses import dataclass

from backend.shared.errors.error_type import ErrorType


@dataclass(slots=True)
class AppError(Exception):
    """内部で扱う構造化エラー。"""

    error_type: ErrorType
    trace: bool
    diagnostic_message: str
    cause: BaseException | None = None

    def __post_init__(self) -> None:
        if not self.trace:
            self.diagnostic_message = ""
        super().__init__(self.diagnostic_message)

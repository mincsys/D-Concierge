from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """run登録結果。"""

    status: Literal["registered", "already_registered", "failed"]
    failure_reason: str | None = None

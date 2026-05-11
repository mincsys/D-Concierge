from dataclasses import dataclass

from backend.application.ports.runtime.dispatch_status import DispatchStatus


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """run登録結果。"""

    status: DispatchStatus
    failure_reason: str | None = None

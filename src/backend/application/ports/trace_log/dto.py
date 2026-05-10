from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TraceLogRecord:
    """障害調査用トレースログ1件分。"""

    trace_id: str
    event_name: str
    stage: str
    chat_id: UUID | None = None
    run_id: UUID | None = None
    error_class: str | None = None
    exception_type: str | None = None
    run_state: str | None = None
    execution_deadline_at: datetime | None = None
    timeout_state: str | None = None
    cancel_state: str | None = None
    retry_count: int | None = None
    validation_failure_reason: str | None = None
    message: str | None = None

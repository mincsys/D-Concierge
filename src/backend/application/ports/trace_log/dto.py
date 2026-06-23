from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class TraceLogRecord:
    """異常系トレースログ1件分のDTO。"""

    occurred_at: datetime
    trace_id: TraceId
    event_name: str
    stage: str
    error_type: ErrorType
    message: str
    exception_type: str
    stacktrace: str
    http_method: str
    path: str
    status_code: int
    user_id: str | None = None
    chat_id: str | None = None
    run_id: str | None = None
    reference_id: str | None = None
    artifact_id: str | None = None

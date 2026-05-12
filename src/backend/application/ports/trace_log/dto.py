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
    user_id: UUID | None = None
    reference_id: UUID | None = None
    artifact_id: UUID | None = None
    error_type: str | None = None
    exception_type: str | None = None
    stacktrace: str | None = None
    http_method: str | None = None
    path: str | None = None
    status_code: int | None = None
    client: str | None = None
    request_validation_errors: str | None = None
    run_state: str | None = None
    execution_deadline_at: datetime | None = None
    timeout_state: str | None = None
    cancel_state: str | None = None
    retry_count: int | None = None
    runner_type: str | None = None
    os_name: str | None = None
    codex_exit_status: str | None = None
    process_result: str | None = None
    validation_failure_reason: str | None = None
    validation_comment: str | None = None
    config_path: str | None = None
    recovery_summary: str | None = None
    failed_recovery_run_id: UUID | None = None
    shutdown_phase: str | None = None
    message: str | None = None

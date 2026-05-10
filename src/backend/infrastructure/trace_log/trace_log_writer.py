import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from backend.application.ports.trace_log.dto import TraceLogRecord

_ABSOLUTE_PATH_PATTERN = re.compile(r"(?<!\w)/(?:[^\s\"']+/)+[^\s\"']*")
_MAX_TEXT_LENGTH = 160


class TraceLogPayload(TypedDict, total=False):
    """JSONLへ保存するトレースログpayload。"""

    occurred_at: str
    trace_id: str
    event_name: str
    stage: str
    chat_id: str
    run_id: str
    error_class: str
    exception_type: str
    run_state: str
    execution_deadline_at: str
    timeout_state: str
    cancel_state: str
    retry_count: int
    validation_failure_reason: str
    message: str


class TraceLogWriter:
    """障害調査用トレースログをJSONLへ追記する。"""

    def __init__(
        self,
        log_dir: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._log_dir = log_dir
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    def write(self, record: TraceLogRecord) -> None:
        """トレースログを1件追記する。書込失敗は主処理へ波及させない。"""
        now = self._clock()
        payload = _to_payload(record, now)
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            with self._log_path(now).open("a", encoding="utf-8") as log_file:
                log_file.write(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                )
        except OSError:
            return

    def _log_path(self, now: datetime) -> Path:
        return self._log_dir / f"trace-{now:%Y%m%d}.jsonl"


def _to_payload(record: TraceLogRecord, now: datetime) -> TraceLogPayload:
    payload = TraceLogPayload(
        occurred_at=now.isoformat(),
        trace_id=record.trace_id,
        event_name=record.event_name,
        stage=record.stage,
    )
    if record.chat_id is not None:
        payload["chat_id"] = str(record.chat_id)
    if record.run_id is not None:
        payload["run_id"] = str(record.run_id)
    if record.error_class is not None:
        payload["error_class"] = _sanitize_text(record.error_class)
    if record.exception_type is not None:
        payload["exception_type"] = _sanitize_text(record.exception_type)
    if record.run_state is not None:
        payload["run_state"] = _sanitize_text(record.run_state)
    if record.execution_deadline_at is not None:
        payload["execution_deadline_at"] = record.execution_deadline_at.isoformat()
    if record.timeout_state is not None:
        payload["timeout_state"] = _sanitize_text(record.timeout_state)
    if record.cancel_state is not None:
        payload["cancel_state"] = _sanitize_text(record.cancel_state)
    if record.retry_count is not None:
        payload["retry_count"] = record.retry_count
    if record.validation_failure_reason is not None:
        payload["validation_failure_reason"] = _sanitize_text(
            record.validation_failure_reason
        )
    if record.message is not None:
        payload["message"] = _sanitize_text(record.message)
    return payload


def _sanitize_text(value: str) -> str:
    sanitized = _ABSOLUTE_PATH_PATTERN.sub("<path>", value)
    if len(sanitized) <= _MAX_TEXT_LENGTH:
        return sanitized
    return sanitized[: _MAX_TEXT_LENGTH - 3] + "..."

import json
import re
import shutil
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TypedDict

from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.shared.tracing.exception import (
    MAX_STACKTRACE_LENGTH,
    limit_trace_text,
)

_FILENAME_EVENT_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_TRACE_LOG_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_RETENTION_DAYS = 90
DEFAULT_MAX_FILES_PER_DAY = 1000


class TraceLogPayload(TypedDict, total=False):
    """JSONへ保存するトレースログpayload。"""

    occurred_at: str
    trace_id: str
    event_name: str
    stage: str
    chat_id: str
    run_id: str
    user_id: str
    reference_id: str
    artifact_id: str
    error_class: str
    exception_type: str
    stacktrace: str
    http_method: str
    path: str
    status_code: int
    client: str
    request_validation_errors: str
    run_state: str
    execution_deadline_at: str
    timeout_state: str
    cancel_state: str
    retry_count: int
    runner_type: str
    os_name: str
    codex_exit_status: str
    process_result: str
    validation_failure_reason: str
    validation_comment: str
    config_path: str
    recovery_summary: str
    failed_recovery_run_id: str
    shutdown_phase: str
    message: str


class TraceLogWriter:
    """障害調査用トレースログを1イベント1JSONファイルへ保存する。"""

    def __init__(
        self,
        log_dir: Path,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_files_per_day: int = DEFAULT_MAX_FILES_PER_DAY,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if retention_days <= 0:
            raise ValueError("retention_days must be positive.")
        if max_files_per_day <= 0:
            raise ValueError("max_files_per_day must be positive.")
        self._log_dir = log_dir
        self._retention_days = retention_days
        self._max_files_per_day = max_files_per_day
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._current_log_date: date | None = None
        self._current_day_written_count = 0

    def cleanup_expired(self) -> None:
        """保存期間を過ぎた日付ディレクトリを削除する。失敗は主処理へ波及させない。"""
        cutoff_date = self._clock().date() - timedelta(days=self._retention_days)
        try:
            entries = list(self._log_dir.iterdir())
        except OSError:
            return
        for entry in entries:
            if not entry.is_dir():
                continue
            try:
                log_date = datetime.strptime(entry.name, _TRACE_LOG_DATE_FORMAT).date()
            except ValueError:
                continue
            if log_date >= cutoff_date:
                continue
            try:
                shutil.rmtree(entry)
            except OSError:
                continue

    def write(self, record: TraceLogRecord) -> None:
        """トレースログを1件保存する。書込失敗は主処理へ波及させない。"""
        now = self._clock()
        self._reset_counter_if_new_day(now.date())
        if self._current_day_written_count >= self._max_files_per_day:
            return
        payload = _to_payload(record, now)
        try:
            day_dir = self._log_dir / f"{now:%Y-%m-%d}"
            day_dir.mkdir(parents=True, exist_ok=True)
            self._write_new_file(day_dir, now, record.event_name, payload)
        except OSError:
            return
        self._current_day_written_count += 1

    def _reset_counter_if_new_day(self, log_date: date) -> None:
        if self._current_log_date == log_date:
            return
        self._current_log_date = log_date
        self._current_day_written_count = 0

    def _write_new_file(
        self,
        day_dir: Path,
        now: datetime,
        event_name: str,
        payload: TraceLogPayload,
    ) -> None:
        base_name = (
            f"{now:%H-%M-%S}_{now.microsecond:06d}_{_safe_event_name(event_name)}"
        )
        suffix = 1
        while True:
            suffix_text = "" if suffix == 1 else f"_{suffix}"
            log_path = day_dir / f"{base_name}{suffix_text}.json"
            try:
                with log_path.open("x", encoding="utf-8") as log_file:
                    log_file.write(json.dumps(payload, ensure_ascii=False, indent=2))
                    log_file.write("\n")
                return
            except FileExistsError:
                suffix += 1


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
    if record.user_id is not None:
        payload["user_id"] = str(record.user_id)
    if record.reference_id is not None:
        payload["reference_id"] = str(record.reference_id)
    if record.artifact_id is not None:
        payload["artifact_id"] = str(record.artifact_id)
    if record.error_class is not None:
        payload["error_class"] = limit_trace_text(record.error_class)
    if record.exception_type is not None:
        payload["exception_type"] = limit_trace_text(record.exception_type)
    if record.stacktrace is not None:
        payload["stacktrace"] = limit_trace_text(
            record.stacktrace, max_length=MAX_STACKTRACE_LENGTH
        )
    if record.http_method is not None:
        payload["http_method"] = limit_trace_text(record.http_method)
    if record.path is not None:
        payload["path"] = limit_trace_text(record.path)
    if record.status_code is not None:
        payload["status_code"] = record.status_code
    if record.client is not None:
        payload["client"] = limit_trace_text(record.client)
    if record.request_validation_errors is not None:
        payload["request_validation_errors"] = limit_trace_text(
            record.request_validation_errors
        )
    if record.run_state is not None:
        payload["run_state"] = limit_trace_text(record.run_state)
    if record.execution_deadline_at is not None:
        payload["execution_deadline_at"] = record.execution_deadline_at.isoformat()
    if record.timeout_state is not None:
        payload["timeout_state"] = limit_trace_text(record.timeout_state)
    if record.cancel_state is not None:
        payload["cancel_state"] = limit_trace_text(record.cancel_state)
    if record.retry_count is not None:
        payload["retry_count"] = record.retry_count
    if record.runner_type is not None:
        payload["runner_type"] = limit_trace_text(record.runner_type)
    if record.os_name is not None:
        payload["os_name"] = limit_trace_text(record.os_name)
    if record.codex_exit_status is not None:
        payload["codex_exit_status"] = limit_trace_text(record.codex_exit_status)
    if record.process_result is not None:
        payload["process_result"] = limit_trace_text(record.process_result)
    if record.validation_failure_reason is not None:
        payload["validation_failure_reason"] = limit_trace_text(
            record.validation_failure_reason
        )
    if record.validation_comment is not None:
        payload["validation_comment"] = limit_trace_text(record.validation_comment)
    if record.config_path is not None:
        payload["config_path"] = limit_trace_text(record.config_path)
    if record.recovery_summary is not None:
        payload["recovery_summary"] = limit_trace_text(record.recovery_summary)
    if record.failed_recovery_run_id is not None:
        payload["failed_recovery_run_id"] = str(record.failed_recovery_run_id)
    if record.shutdown_phase is not None:
        payload["shutdown_phase"] = limit_trace_text(record.shutdown_phase)
    if record.message is not None:
        payload["message"] = limit_trace_text(record.message)
    return payload


def _safe_event_name(event_name: str) -> str:
    safe = _FILENAME_EVENT_PATTERN.sub("_", event_name).strip("_")
    if safe == "":
        return "trace"
    return safe

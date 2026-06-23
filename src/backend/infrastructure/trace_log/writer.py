from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from shutil import rmtree
from typing import TypedDict
from zoneinfo import ZoneInfo

import yaml

from backend.application.ports.trace_log.dto import TraceLogRecord


class TraceLogYamlPayload(TypedDict):
    occurred_at: str
    trace_id: str
    event_name: str
    stage: str
    user_id: str | None
    chat_id: str | None
    run_id: str | None
    reference_id: str | None
    artifact_id: str | None
    error_type: str
    message: str
    exception_type: str
    stacktrace: str
    http_method: str
    path: str
    status_code: int


@dataclass(slots=True)
class TraceLogWriter:
    """異常系トレースログを1件1YAMLファイルで保存する。"""

    root_dir: Path
    timezone: ZoneInfo | str
    retention_days: int
    max_files_per_day: int
    _current_count_date: date | None = field(default=None, init=False)
    _successful_write_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if isinstance(self.timezone, str):
            self.timezone = ZoneInfo(self.timezone)

    def prune_expired(self, now: datetime | None = None) -> None:
        """保持期間を過ぎた日付ディレクトリを削除する。"""

        if not self.root_dir.exists():
            return
        timezone = self._timezone()
        current_date = (
            (now or datetime.now(timezone))
            .astimezone(
                timezone,
            )
            .date()
        )
        oldest_kept_date = current_date - timedelta(days=self.retention_days)
        for child_path in self.root_dir.iterdir():
            if not child_path.is_dir():
                continue
            try:
                child_date = datetime.strptime(child_path.name, "%Y-%m-%d").date()
            except ValueError:
                continue
            if child_date < oldest_kept_date:
                rmtree(child_path)

    def write(self, record: TraceLogRecord) -> Path:
        occurred_at = record.occurred_at.astimezone(self._timezone())
        date_dir = self.root_dir / occurred_at.strftime("%Y-%m-%d")
        self._reset_count_if_date_changed(occurred_at.date())
        if self._successful_write_count >= self.max_files_per_day:
            raise RuntimeError("同日のトレースログ最大保存件数を超えました。")
        date_dir.mkdir(parents=True, exist_ok=True)

        payload = self._to_payload(record)
        log_path = self._unique_log_path(
            date_dir,
            occurred_at.strftime("%H-%M-%S_%f"),
            record.event_name,
        )
        log_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self._successful_write_count += 1
        return log_path

    def _reset_count_if_date_changed(self, occurred_date: date) -> None:
        if self._current_count_date == occurred_date:
            return
        self._current_count_date = occurred_date
        self._successful_write_count = 0

    def _to_payload(self, record: TraceLogRecord) -> TraceLogYamlPayload:
        occurred_at = record.occurred_at.astimezone(self._timezone())
        return {
            "occurred_at": occurred_at.isoformat(),
            "trace_id": str(record.trace_id),
            "event_name": record.event_name,
            "stage": record.stage,
            "user_id": record.user_id,
            "chat_id": record.chat_id,
            "run_id": record.run_id,
            "reference_id": record.reference_id,
            "artifact_id": record.artifact_id,
            "error_type": record.error_type.value,
            "message": record.message[: 64 * 1024],
            "exception_type": record.exception_type,
            "stacktrace": record.stacktrace[: 1024 * 1024],
            "http_method": record.http_method,
            "path": record.path,
            "status_code": record.status_code,
        }

    def _timezone(self) -> ZoneInfo:
        if isinstance(self.timezone, str):
            self.timezone = ZoneInfo(self.timezone)
        return self.timezone

    def _unique_log_path(
        self,
        date_dir: Path,
        timestamp_part: str,
        event_name: str,
    ) -> Path:
        base_name = f"{timestamp_part}_{event_name}"
        candidate = date_dir / f"{base_name}.yaml"
        sequence = 1
        while candidate.exists():
            candidate = date_dir / f"{base_name}_{sequence}.yaml"
            sequence += 1
        return candidate

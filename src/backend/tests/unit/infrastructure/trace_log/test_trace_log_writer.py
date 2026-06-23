from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.infrastructure.trace_log.writer import TraceLogWriter
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId


def test_trace_log_daily_limit_ignores_files_that_existed_before_startup(
    tmp_path: Path,
) -> None:
    """
    観点：トレースログ同日最大保存件数がアプリケーション起動後の成功書込件数だけで判定されること
    確認：同日ディレクトリに起動前ファイルが存在しても初回書込は許可され、起動後成功件数が上限に達した後だけ拒否されること
    """
    occurred_at = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    date_dir = tmp_path / "2026-01-01"
    date_dir.mkdir()
    (date_dir / "before-startup.yaml").write_text("old: true\n", encoding="utf-8")
    writer = TraceLogWriter(
        root_dir=tmp_path,
        timezone=ZoneInfo("UTC"),
        retention_days=90,
        max_files_per_day=1,
    )

    log_path = writer.write(_trace_log_record(occurred_at))

    assert log_path.exists()
    assert len(tuple(date_dir.glob("*.yaml"))) == 2
    with pytest.raises(RuntimeError, match="最大保存件数"):
        writer.write(_trace_log_record(occurred_at, event_name="api_failed_again"))


def test_trace_log_daily_limit_resets_when_date_changes(tmp_path: Path) -> None:
    """
    観点：トレースログ同日最大保存件数の起動後カウンタが日付単位で管理されること
    確認：同日に上限到達した後でも、発生日付が変わればカウンタが0に戻り保存を再開できること
    """
    writer = TraceLogWriter(
        root_dir=tmp_path,
        timezone=ZoneInfo("UTC"),
        retention_days=90,
        max_files_per_day=1,
    )
    first_day = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    second_day = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)

    writer.write(_trace_log_record(first_day))
    with pytest.raises(RuntimeError, match="最大保存件数"):
        writer.write(_trace_log_record(first_day, event_name="same_day"))

    assert writer.write(_trace_log_record(second_day)).exists()


def test_trace_log_daily_limit_does_not_count_failed_writes(tmp_path: Path) -> None:
    """
    観点：トレースログ書込失敗時に起動後成功書込件数が増えないこと
    確認：不正なイベント名でファイル書込に失敗した後、同日の正常な初回書込は上限内として成功すること
    """
    writer = TraceLogWriter(
        root_dir=tmp_path,
        timezone=ZoneInfo("UTC"),
        retention_days=90,
        max_files_per_day=1,
    )
    occurred_at = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    with pytest.raises(FileNotFoundError):
        writer.write(_trace_log_record(occurred_at, event_name="invalid/event"))

    assert writer.write(_trace_log_record(occurred_at)).exists()
    with pytest.raises(RuntimeError, match="最大保存件数"):
        writer.write(_trace_log_record(occurred_at, event_name="after_success"))


def test_trace_log_prune_expired_removes_only_expired_date_directories(
    tmp_path: Path,
) -> None:
    """
    観点：トレースログ保持期間削除が日付ディレクトリだけを対象にすること
    確認：保存期間外の日付ディレクトリだけを削除し、保持対象日、日付形式外ディレクトリ、通常ファイル、未作成rootはエラーなく残すこと
    """
    missing_root_writer = TraceLogWriter(
        root_dir=tmp_path / "missing",
        timezone=ZoneInfo("UTC"),
        retention_days=1,
        max_files_per_day=1000,
    )
    missing_root_writer.prune_expired(now=datetime(2026, 1, 10, 0, 0, tzinfo=UTC))

    root_dir = tmp_path / "trace_log"
    expired_dir = root_dir / "2026-01-08"
    oldest_kept_dir = root_dir / "2026-01-09"
    today_dir = root_dir / "2026-01-10"
    non_date_dir = root_dir / "not-date"
    for directory in (expired_dir, oldest_kept_dir, today_dir, non_date_dir):
        directory.mkdir(parents=True)
        (directory / "trace.yaml").write_text("exists: true\n", encoding="utf-8")
    regular_file = root_dir / "2026-01-07.yaml"
    regular_file.write_text("file: true\n", encoding="utf-8")
    writer = TraceLogWriter(
        root_dir=root_dir,
        timezone=ZoneInfo("UTC"),
        retention_days=1,
        max_files_per_day=1000,
    )

    writer.prune_expired(now=datetime(2026, 1, 10, 0, 0, tzinfo=UTC))

    assert not expired_dir.exists()
    assert oldest_kept_dir.exists()
    assert today_dir.exists()
    assert non_date_dir.exists()
    assert regular_file.exists()


def test_trace_log_writer_adds_sequence_when_log_file_name_collides(
    tmp_path: Path,
) -> None:
    """
    観点：同一時刻と同一イベント名のトレースログが既存ファイルを上書きしないこと
    確認：同じ発生日時とevent_nameで複数回保存した場合、2件目は連番付きファイル名で保存されること
    """
    writer = TraceLogWriter(
        root_dir=tmp_path,
        timezone=ZoneInfo("UTC"),
        retention_days=90,
        max_files_per_day=2,
    )
    occurred_at = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    first_path = writer.write(_trace_log_record(occurred_at))
    second_path = writer.write(_trace_log_record(occurred_at))

    assert first_path.name == "00-00-00_000000_api_failed.yaml"
    assert second_path.name == "00-00-00_000000_api_failed_1.yaml"


def _trace_log_record(
    occurred_at: datetime,
    *,
    event_name: str = "api_failed",
) -> TraceLogRecord:
    return TraceLogRecord(
        occurred_at=occurred_at,
        trace_id=TraceId("018f0000-0000-7000-8000-000000000001"),
        event_name=event_name,
        stage="presentation.rest",
        error_type=ErrorType.SYSTEM,
        message="テスト用エラー",
        exception_type="RuntimeError",
        stacktrace="stack",
        http_method="GET",
        path="/api/test",
        status_code=500,
    )

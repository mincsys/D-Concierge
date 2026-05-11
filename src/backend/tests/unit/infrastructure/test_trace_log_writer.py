import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pytest import MonkeyPatch

from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter


def test_trace_log_writer_writes_pretty_json_file_without_masking(
    tmp_path: Path,
) -> None:
    """観点：TraceLogWriter。確認：1イベント1JSONで、開発者向け情報をマスクしない。"""
    writer = TraceLogWriter(
        log_dir=tmp_path,
        clock=lambda: datetime(2026, 5, 9, 10, 0, 1, 234567, tzinfo=UTC),
    )

    writer.write(
        TraceLogRecord(
            trace_id="trace-701",
            event_name="execution/failed",
            stage="generation",
            chat_id=UUID("00000000-0000-0000-0000-000000000701"),
            run_id=UUID("00000000-0000-0000-0000-000000000702"),
            error_class="system",
            exception_type="AppError",
            message=(
                "/home/minami/dev/D-Concierge/codex/secret "
                "Authorization: Bearer token-value"
            ),
            stacktrace="Traceback...\nRuntimeError: failed",
        )
    )

    log_path = tmp_path / "2026-05-09" / "10-00-01_234567_execution_failed.json"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["trace_id"] == "trace-701"
    assert payload["event_name"] == "execution/failed"
    assert payload["chat_id"] == "00000000-0000-0000-0000-000000000701"
    assert "/home/minami/dev/D-Concierge/codex/secret" in payload["message"]
    assert "Authorization: Bearer token-value" in payload["message"]
    assert "\n  " in log_path.read_text(encoding="utf-8")


def test_trace_log_writer_writes_optional_diagnostic_fields(
    tmp_path: Path,
) -> None:
    """観点：TraceLogWriter。確認：異常調査用の任意診断項目を保存する。"""
    writer = TraceLogWriter(
        log_dir=tmp_path,
        clock=lambda: datetime(2026, 5, 9, 10, 5, tzinfo=UTC),
    )

    writer.write(
        TraceLogRecord(
            trace_id="trace-702",
            event_name="validation_failed",
            stage="validation",
            run_state="エラー",
            timeout_state="none",
            cancel_state="none",
            retry_count=2,
            validation_failure_reason="参照元不足",
            validation_comment="最後の検証結果",
            runner_type="validator",
            codex_exit_status="failed",
            process_result="exit 1",
        )
    )

    [log_path] = list((tmp_path / "2026-05-09").glob("*.json"))
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["run_state"] == "エラー"
    assert payload["timeout_state"] == "none"
    assert payload["cancel_state"] == "none"
    assert payload["retry_count"] == 2
    assert payload["validation_failure_reason"] == "参照元不足"
    assert payload["validation_comment"] == "最後の検証結果"
    assert payload["runner_type"] == "validator"
    assert payload["codex_exit_status"] == "failed"
    assert payload["process_result"] == "exit 1"


def test_trace_log_writer_appends_suffix_when_filename_collides(tmp_path: Path) -> None:
    """観点：TraceLogWriter。確認：同一時刻・同一イベント名でもファイルを上書きしない。"""
    now = datetime(2026, 5, 9, 10, 5, tzinfo=UTC)
    writer = TraceLogWriter(log_dir=tmp_path, clock=lambda: now)

    writer.write(
        TraceLogRecord(trace_id="trace-1", event_name="api_failed", stage="api")
    )
    writer.write(
        TraceLogRecord(trace_id="trace-2", event_name="api_failed", stage="api")
    )

    paths = sorted(path.name for path in (tmp_path / "2026-05-09").glob("*.json"))
    assert paths == [
        "10-05-00_000000_api_failed.json",
        "10-05-00_000000_api_failed_2.json",
    ]


def test_trace_log_writer_limits_huge_text_without_masking(tmp_path: Path) -> None:
    """観点：TraceLogWriter。確認：巨大文字列だけを上限で切り詰める。"""
    writer = TraceLogWriter(
        log_dir=tmp_path,
        clock=lambda: datetime(2026, 5, 9, 10, 5, tzinfo=UTC),
    )

    writer.write(
        TraceLogRecord(
            trace_id="trace-703",
            event_name="execution_failed",
            stage="execution",
            message="/tmp/secret " + ("x" * 70_000),
        )
    )

    [log_path] = list((tmp_path / "2026-05-09").glob("*.json"))
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["message"].startswith("/tmp/secret ")
    assert payload["message"].endswith("...<truncated>")
    assert len(payload["message"]) <= 65_536 + len("...<truncated>")


def test_trace_log_writer_cleanup_expired_deletes_old_date_directories(
    tmp_path: Path,
) -> None:
    """観点：TraceLogWriter。確認：保存期間を超えた日付ディレクトリだけを削除する。"""
    old_dir = tmp_path / "2026-02-07"
    boundary_dir = tmp_path / "2026-02-08"
    current_dir = tmp_path / "2026-05-09"
    ignored_dir = tmp_path / "not-a-date"
    ignored_file = tmp_path / "2026-01-01.json"
    for directory in (old_dir, boundary_dir, current_dir, ignored_dir):
        directory.mkdir()
        (directory / "trace.json").write_text("{}", encoding="utf-8")
    ignored_file.write_text("{}", encoding="utf-8")
    writer = TraceLogWriter(
        log_dir=tmp_path,
        retention_days=90,
        max_files_per_day=1000,
        clock=lambda: datetime(2026, 5, 9, tzinfo=UTC),
    )

    writer.cleanup_expired()

    assert old_dir.exists() is False
    assert boundary_dir.exists()
    assert current_dir.exists()
    assert ignored_dir.exists()
    assert ignored_file.exists()


def test_trace_log_writer_cleanup_expired_ignores_delete_failure(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """観点：TraceLogWriter。確認：期限超過ログの削除失敗は呼出元へ波及しない。"""
    old_dir = tmp_path / "2026-02-07"
    old_dir.mkdir()
    (old_dir / "trace.json").write_text("{}", encoding="utf-8")
    writer = TraceLogWriter(
        log_dir=tmp_path,
        retention_days=90,
        max_files_per_day=1000,
        clock=lambda: datetime(2026, 5, 9, tzinfo=UTC),
    )

    def fail_delete(_path: Path) -> None:
        raise OSError

    monkeypatch.setattr(
        "backend.infrastructure.trace_log.trace_log_writer.shutil.rmtree",
        fail_delete,
    )

    writer.cleanup_expired()

    assert old_dir.exists()


def test_trace_log_writer_limits_written_files_per_process_day(tmp_path: Path) -> None:
    """観点：TraceLogWriter。確認：起動後同日上限を超えたログは保存しない。"""
    writer = TraceLogWriter(
        log_dir=tmp_path,
        retention_days=90,
        max_files_per_day=2,
        clock=lambda: datetime(2026, 5, 9, 10, 5, tzinfo=UTC),
    )
    existing = tmp_path / "2026-05-09"
    existing.mkdir()
    (existing / "existing.json").write_text("{}", encoding="utf-8")

    writer.write(
        TraceLogRecord(trace_id="trace-1", event_name="api_failed", stage="api")
    )
    writer.write(
        TraceLogRecord(trace_id="trace-2", event_name="api_failed", stage="api")
    )
    writer.write(
        TraceLogRecord(trace_id="trace-3", event_name="api_failed", stage="api")
    )

    paths = sorted(path.name for path in existing.glob("*.json"))
    assert paths == [
        "10-05-00_000000_api_failed.json",
        "10-05-00_000000_api_failed_2.json",
        "existing.json",
    ]


def test_trace_log_writer_does_not_increment_limit_on_write_failure(
    tmp_path: Path,
) -> None:
    """観点：TraceLogWriter。確認：書込失敗時は同日保存件数を増やさない。"""
    log_dir = tmp_path / "logs"
    log_dir.write_text("not directory", encoding="utf-8")
    writer = TraceLogWriter(
        log_dir=log_dir,
        retention_days=90,
        max_files_per_day=1,
        clock=lambda: datetime(2026, 5, 9, 10, 5, tzinfo=UTC),
    )

    writer.write(
        TraceLogRecord(trace_id="trace-1", event_name="api_failed", stage="api")
    )
    log_dir.unlink()
    writer.write(
        TraceLogRecord(trace_id="trace-2", event_name="api_failed", stage="api")
    )
    writer.write(
        TraceLogRecord(trace_id="trace-3", event_name="api_failed", stage="api")
    )

    paths = sorted(path.name for path in (log_dir / "2026-05-09").glob("*.json"))
    assert paths == ["10-05-00_000000_api_failed.json"]


def test_trace_log_writer_resets_daily_limit_when_date_changes(tmp_path: Path) -> None:
    """観点：TraceLogWriter。確認：日付が変わると起動後同日カウンタを初期化する。"""
    timestamps = iter(
        (
            datetime(2026, 5, 9, 23, 59, tzinfo=UTC),
            datetime(2026, 5, 9, 23, 59, tzinfo=UTC),
            datetime(2026, 5, 10, 0, 0, tzinfo=UTC),
        )
    )
    writer = TraceLogWriter(
        log_dir=tmp_path,
        retention_days=90,
        max_files_per_day=1,
        clock=lambda: next(timestamps),
    )

    writer.write(
        TraceLogRecord(trace_id="trace-1", event_name="api_failed", stage="api")
    )
    writer.write(
        TraceLogRecord(trace_id="trace-2", event_name="api_failed", stage="api")
    )
    writer.write(
        TraceLogRecord(trace_id="trace-3", event_name="api_failed", stage="api")
    )

    assert len(list((tmp_path / "2026-05-09").glob("*.json"))) == 1
    assert len(list((tmp_path / "2026-05-10").glob("*.json"))) == 1

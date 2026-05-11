import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

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

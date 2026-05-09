from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.shared.tracing import TraceLogRecord


def test_trace_log_writer_writes_jsonl_record_with_sanitized_message(
    tmp_path: Path,
) -> None:
    """観点：TraceLogWriter。確認：JSONLを追記し、絶対パスと長文を保存しない。"""
    writer = TraceLogWriter(
        log_dir=tmp_path,
        clock=lambda: datetime(2026, 5, 9, 10, 0, tzinfo=UTC),
    )

    writer.write(
        TraceLogRecord(
            trace_id="trace-701",
            event_name="execution_failed",
            stage="generation",
            chat_id=UUID("00000000-0000-0000-0000-000000000701"),
            run_id=UUID("00000000-0000-0000-0000-000000000702"),
            error_class="system",
            exception_type="AppError",
            message="/home/minami/dev/D-Concierge/codex/secret " + ("x" * 240),
        )
    )

    log_path = tmp_path / "trace-20260509.jsonl"
    line = log_path.read_text(encoding="utf-8").strip()
    assert '"trace_id":"trace-701"' in line
    assert '"event_name":"execution_failed"' in line
    assert '"chat_id":"00000000-0000-0000-0000-000000000701"' in line
    assert "/home/minami" not in line
    assert len(line) < 520


def test_trace_log_writer_writes_optional_diagnostic_fields(
    tmp_path: Path,
) -> None:
    """観点：TraceLogWriter。確認：任意の診断項目をJSONLへ保存する。"""
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
        )
    )

    line = (tmp_path / "trace-20260509.jsonl").read_text(encoding="utf-8").strip()
    assert '"run_state":"エラー"' in line
    assert '"timeout_state":"none"' in line
    assert '"cancel_state":"none"' in line
    assert '"retry_count":2' in line
    assert '"validation_failure_reason":"参照元不足"' in line

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI

from backend.app.factory import create_app
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.infrastructure.config.loader import ConfigLoader
from backend.infrastructure.config.models import TraceLogConfig
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.shared.errors import ErrorClass
from backend.shared.tracing.exception import exception_message, exception_stacktrace

_CONFIG_PATH = Path("config.yaml")


def _create_app_with_bootstrap_trace() -> FastAPI:
    try:
        return create_app()
    except Exception as exc:
        trace_log_config = _bootstrap_trace_log_config()
        trace_logger = TraceLogWriter(
            trace_log_config.dir,
            retention_days=trace_log_config.retention_days,
            max_files_per_day=trace_log_config.max_files_per_day,
        )
        trace_logger.write(
            TraceLogRecord(
                trace_id=str(uuid4()),
                event_name="app_bootstrap_failed",
                stage="app_bootstrap",
                error_class=ErrorClass.SYSTEM.value,
                exception_type=type(exc).__name__,
                stacktrace=exception_stacktrace(exc),
                config_path=str(_CONFIG_PATH),
                message=exception_message(exc),
            )
        )
        raise


def _bootstrap_trace_log_config() -> TraceLogConfig:
    try:
        return ConfigLoader.load(_CONFIG_PATH).trace_log
    except Exception:
        return TraceLogConfig(
            dir=Path("logs/trace"),
            retention_days=90,
            max_files_per_day=1000,
        )


app = _create_app_with_bootstrap_trace()

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from backend.app.factory import create_app
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.infrastructure.config.loader import ConfigLoader
from backend.infrastructure.config.models import TraceLogConfig
from backend.infrastructure.runtime.system_clock import SystemClock
from backend.infrastructure.runtime.uuid_generator import UuidGenerator
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.exception import exception_message, exception_stacktrace

_CONFIG_PATH = Path("config.yaml")
_DEFAULT_TIMEZONE = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True, slots=True)
class _BootstrapTraceLogSettings:
    """起動失敗時トレースログの最低限設定。"""

    trace_log: TraceLogConfig
    timezone: ZoneInfo


def _create_app_with_bootstrap_trace() -> FastAPI:
    try:
        return create_app()
    except Exception as exc:
        trace_log_settings = _bootstrap_trace_log_settings()
        clock = SystemClock(trace_log_settings.timezone)
        trace_logger = TraceLogWriter(
            trace_log_settings.trace_log.dir,
            retention_days=trace_log_settings.trace_log.retention_days,
            max_files_per_day=trace_log_settings.trace_log.max_files_per_day,
            clock=clock.now_app_timezone,
        )
        trace_logger.write(
            TraceLogRecord(
                trace_id=str(UuidGenerator().new_uuid()),
                event_name="app_bootstrap_failed",
                stage="app_bootstrap",
                error_type=ErrorType.SYSTEM.value,
                exception_type=type(exc).__name__,
                stacktrace=exception_stacktrace(exc),
                config_path=str(_CONFIG_PATH),
                message=exception_message(exc),
            )
        )
        raise


def _bootstrap_trace_log_settings() -> _BootstrapTraceLogSettings:
    try:
        app_config = ConfigLoader.load(_CONFIG_PATH)
        return _BootstrapTraceLogSettings(
            trace_log=app_config.trace_log,
            timezone=app_config.app.timezone,
        )
    except Exception:
        return _BootstrapTraceLogSettings(
            trace_log=TraceLogConfig(
                dir=Path("logs/trace"),
                retention_days=90,
                max_files_per_day=1000,
            ),
            timezone=_DEFAULT_TIMEZONE,
        )


app = _create_app_with_bootstrap_trace()

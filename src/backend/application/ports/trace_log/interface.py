from typing import Protocol

from backend.application.ports.trace_log.dto import TraceLogRecord


class TraceLoggerPort(Protocol):
    """トレースログ出力境界。"""

    def write(self, record: TraceLogRecord) -> None:
        """トレースログを1件出力する。"""

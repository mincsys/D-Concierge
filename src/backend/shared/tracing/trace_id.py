from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid7

from backend.application.ports.runtime.interface import IdGeneratorPort


@dataclass(frozen=True, slots=True)
class TraceId:
    """REST、SSE、トレースログを関連付けるID。"""

    value: str

    def __str__(self) -> str:
        return self.value


class DefaultTraceIdGenerator:
    """trace_id用UUIDv7の既定発番実装。"""

    def new_uuid(self) -> UUID:
        return uuid7()


def new_trace_id(
    id_generator: IdGeneratorPort | None = None,
) -> TraceId:
    """新しいtrace_idを生成する。"""

    generator = id_generator if id_generator is not None else DefaultTraceIdGenerator()
    return TraceId(str(generator.new_uuid()))

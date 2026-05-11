from dataclasses import dataclass
from uuid import UUID

from fastapi import Request


@dataclass(slots=True)
class RequestTraceContext:
    """APIリクエスト中のトレースログ文脈。"""

    stage: str = "api"
    chat_id: UUID | None = None
    run_id: UUID | None = None
    reference_id: UUID | None = None
    artifact_id: UUID | None = None


def ensure_request_trace_context(request: Request) -> RequestTraceContext:
    """request.stateへトレースログ文脈を用意して返す。"""
    context = getattr(request.state, "trace_context", None)
    if isinstance(context, RequestTraceContext):
        return context
    context = RequestTraceContext()
    request.state.trace_context = context
    return context


def request_trace_id(request: Request, fallback: str) -> str:
    """request.state上のtrace_idを返し、未設定ならfallbackを保存して返す。"""
    trace_id = getattr(request.state, "trace_id", None)
    if isinstance(trace_id, str) and trace_id != "":
        return trace_id
    request.state.trace_id = fallback
    return fallback

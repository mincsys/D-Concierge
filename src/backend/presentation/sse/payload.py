from __future__ import annotations

import json
from typing import TypedDict

from backend.application.execution.run_event_broker import RunEvent, RunEventType


class StateEventPayload(TypedDict):
    run_id: str
    state: str


class MessageEventPayload(TypedDict):
    run_id: str
    text: str


class EndEventPayload(TypedDict):
    run_id: str
    state: str
    user_message: str


class PdfLocatorPayload(TypedDict):
    page_start: int
    page_end: int


class ReferencePayload(TypedDict):
    source_type: str
    label: str
    url: str
    locator: PdfLocatorPayload


class AnswerBlockPayload(TypedDict):
    markdown: str
    references: list[ReferencePayload]


class AnswerPayload(TypedDict):
    blocks: list[AnswerBlockPayload]


class AnswerEventPayload(TypedDict):
    run_id: str
    state: str
    answer: AnswerPayload


SsePayload = (
    StateEventPayload | MessageEventPayload | EndEventPayload | AnswerEventPayload
)


def format_sse_event(event: RunEvent) -> str:
    """runイベントをSSE wire形式へ変換する。"""

    return _format_event(event.event_type.value, _payload_for_event(event))


def format_sse_data(event_name: str, payload: SsePayload) -> str:
    """指定payloadをSSE wire形式へ変換する。"""

    return _format_event(event_name, payload)


def _format_event(event_name: str, payload: SsePayload) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {data}\n\n"


def _payload_for_event(event: RunEvent) -> SsePayload:
    if event.event_type is RunEventType.MESSAGE:
        return {
            "run_id": str(event.run_id),
            "text": event.text if event.text is not None else "",
        }
    if event.event_type is RunEventType.STATE:
        return {
            "run_id": str(event.run_id),
            "state": event.payload_state if event.payload_state is not None else "",
        }
    return {
        "run_id": str(event.run_id),
        "state": event.payload_state if event.payload_state is not None else "",
        "user_message": event.user_message if event.user_message is not None else "",
    }

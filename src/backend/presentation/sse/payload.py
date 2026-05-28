import json
from typing import TypedDict
from uuid import UUID

from backend.application.execution.execute_chat_run import RunEvent
from backend.application.execution.run_event_type import RunEventType
from backend.application.ports.database.dto import AnswerData
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


class PdfLocatorPayload(TypedDict):
    """SSE回答内のPDF locator payload。"""

    page_start: int
    page_end: int


class DisplayReferencePayload(TypedDict):
    """SSE回答内の表示用参照元payload。"""

    source_type: str
    label: str
    url: str
    locator: PdfLocatorPayload


class AnswerPayload(TypedDict):
    """SSE回答表示payload。"""

    blocks: list[AnswerBlockPayload]


class AnswerBlockPayload(TypedDict):
    """SSE回答ブロック表示payload。"""

    markdown: str
    references: list[DisplayReferencePayload]


class StateEventPayload(TypedDict):
    """SSE state payload。"""

    run_id: str
    state: str


class MessageEventPayload(TypedDict):
    """SSE message payload。"""

    run_id: str
    text: str


class AnswerEventPayload(TypedDict):
    """SSE answer payload。"""

    run_id: str
    state: str
    answer: AnswerPayload


class EndEventPayload(TypedDict):
    """SSE error/canceled payload。"""

    run_id: str
    state: str
    user_message: str


type SsePayload = (
    StateEventPayload | MessageEventPayload | AnswerEventPayload | EndEventPayload
)


def sse_event_bytes(event_name: str, payload: SsePayload) -> bytes:
    """SSEイベント名とpayloadをwire形式のbytesへ変換する。"""
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {payload_json}\n\n".encode()


def run_event_payload(event: RunEvent) -> SsePayload:
    """アプリ内部のrunイベントをSSE payloadへ変換する。"""
    match event.event:
        case RunEventType.STATE:
            return state_payload(event.run_id, _required_state_value(event))
        case RunEventType.MESSAGE:
            return message_payload(event.run_id, event.text or "")
        case RunEventType.ANSWER:
            if event.answer is None:
                raise AppError(
                    ErrorType.SYSTEM,
                    trace=True,
                    diagnostic_message="回答イベントの内容が不正です。",
                )
            return AnswerEventPayload(
                run_id=str(event.run_id),
                state=_required_state_value(event),
                answer=_answer_payload(event.answer),
            )
        case RunEventType.ERROR | RunEventType.CANCELED:
            return end_payload(
                event.run_id,
                _required_state_value(event),
                event.user_message or "",
            )


def state_payload(run_id: UUID, state: str) -> StateEventPayload:
    """stateイベントpayloadを生成する。"""
    return StateEventPayload(run_id=str(run_id), state=state)


def message_payload(run_id: UUID, text: str) -> MessageEventPayload:
    """messageイベントpayloadを生成する。"""
    return MessageEventPayload(run_id=str(run_id), text=text)


def end_payload(run_id: UUID, state: str, user_message: str) -> EndEventPayload:
    """error/canceledイベントpayloadを生成する。"""
    return EndEventPayload(
        run_id=str(run_id),
        state=state,
        user_message=user_message,
    )


def _required_state_value(event: RunEvent) -> str:
    if event.state is None:
        raise AppError(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="状態イベントの内容が不正です。",
        )
    return event.state.value


def _answer_payload(answer: AnswerData) -> AnswerPayload:
    return AnswerPayload(
        blocks=[
            AnswerBlockPayload(
                markdown=block.markdown,
                references=[
                    DisplayReferencePayload(
                        source_type=reference.source_type.value,
                        label=reference.label,
                        url=f"/api/references/{reference.reference_id}",
                        locator=PdfLocatorPayload(
                            page_start=reference.page_start,
                            page_end=reference.page_end,
                        ),
                    )
                    for reference in block.references
                ],
            )
            for block in answer.blocks
        ],
    )

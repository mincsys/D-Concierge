from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import NotRequired, TypedDict
from uuid import UUID

from backend.application.execution.dto import CodexCancelResult, CodexCancelStatus
from backend.domain.execution.run_state import RunState
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    FIXED_CHAT_NOW,
    RUN_ID_VALUE,
    TRACE_ID_VALUE,
)

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class SsePayload(TypedDict, total=False):
    run_id: str
    state: str
    text: str
    answer: AnswerSseBody
    user_message: str


class AnswerSseBody(TypedDict):
    blocks: list[AnswerBlockSsePayload]


class PdfLocatorSsePayload(TypedDict):
    page_start: int
    page_end: int


class AnswerReferenceSsePayload(TypedDict):
    source_type: str
    label: str
    url: str
    locator: PdfLocatorSsePayload


class AnswerBlockSsePayload(TypedDict):
    markdown: str
    references: NotRequired[list[AnswerReferenceSsePayload]]


@dataclass(frozen=True, slots=True)
class SseWireEvent:
    event: str
    payload: SsePayload


@dataclass(frozen=True, slots=True)
class CancelRunTargetRecord:
    user_id: str
    chat_id: UUID
    run_id: UUID
    state: str
    chat_state: str = "active"


@dataclass(frozen=True, slots=True)
class StateTransitionRecord:
    run_id: UUID
    expected_state: str
    next_state: str
    user_message: str | None


@dataclass(frozen=True, slots=True)
class PublishedRunEventRecord:
    run_id: UUID
    event_name: str
    payload_state: str
    user_message: str | None = None


@dataclass(frozen=True, slots=True)
class CancelRequestRecord:
    chat_id: UUID
    run_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class RecoveryRunRecord:
    chat_id: UUID
    run_id: UUID
    state: str
    trace_id: str


@dataclass(slots=True)
class FakeExecutionRepository:
    cancel_targets: dict[tuple[str, UUID, UUID], CancelRunTargetRecord] = field(
        default_factory=dict,
    )
    unfinished_runs: list[RecoveryRunRecord] = field(default_factory=list)
    transitions: list[StateTransitionRecord] = field(default_factory=list)
    fail_update_run_ids: set[UUID] = field(default_factory=set)
    fail_next_states: set[str] = field(default_factory=set)

    def get_cancel_target(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
    ) -> CancelRunTargetRecord | None:
        return self.cancel_targets.get((user_id, chat_id, run_id))

    def update_run_state_if_current(
        self,
        run_id: UUID,
        expected_state: str,
        next_state: str,
        user_message: str | None = None,
    ) -> bool:
        self.transitions.append(
            StateTransitionRecord(
                run_id=run_id,
                expected_state=expected_state,
                next_state=next_state,
                user_message=user_message,
            )
        )
        return run_id not in self.fail_update_run_ids and next_state not in (
            self.fail_next_states
        )

    def list_unfinished_runs_for_recovery(self) -> tuple[RecoveryRunRecord, ...]:
        return tuple(self.unfinished_runs)


@dataclass(slots=True)
class FakeRunEventPublisher:
    events: list[PublishedRunEventRecord] = field(default_factory=list)

    def publish(
        self,
        run_id: UUID,
        event_name: str,
        payload_state: str,
        user_message: str | None = None,
    ) -> None:
        self.events.append(
            PublishedRunEventRecord(
                run_id=run_id,
                event_name=event_name,
                payload_state=payload_state,
                user_message=user_message,
            )
        )


@dataclass(slots=True)
class FakeCodexRunner:
    next_cancel_result: CodexCancelStatus = "sent"
    cancel_requests: list[CancelRequestRecord] = field(default_factory=list)

    def cancel(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> CodexCancelResult:
        self.cancel_requests.append(
            CancelRequestRecord(chat_id=chat_id, run_id=run_id, trace_id=trace_id),
        )
        return CodexCancelResult(status=self.next_cancel_result)


@dataclass(slots=True)
class FakeBackgroundExecutor:
    submitted_run_ids: list[UUID] = field(default_factory=list)
    fail_on_run_ids: set[UUID] = field(default_factory=set)

    def submit(self, run_id: UUID) -> bool:
        self.submitted_run_ids.append(run_id)
        return run_id not in self.fail_on_run_ids


def accepted_cancel_target() -> CancelRunTargetRecord:
    return CancelRunTargetRecord(
        user_id="user-001",
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        state=RunState.ACCEPTED.value,
    )


def running_cancel_target() -> CancelRunTargetRecord:
    return CancelRunTargetRecord(
        user_id="user-001",
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        state=RunState.RUNNING.value,
    )


def recovery_run(state: RunState, run_id: UUID = RUN_ID_VALUE) -> RecoveryRunRecord:
    return RecoveryRunRecord(
        chat_id=CHAT_ID_VALUE,
        run_id=run_id,
        state=state.value,
        trace_id=TRACE_ID_VALUE,
    )


def parse_sse_events(response_text: str) -> tuple[SseWireEvent, ...]:
    events: list[SseWireEvent] = []
    current_event = ""
    data_lines: list[str] = []

    for line in response_text.splitlines():
        if line == "":
            if current_event and data_lines:
                events.append(_parse_sse_event(current_event, "\n".join(data_lines)))
            current_event = ""
            data_lines = []
            continue
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ")
            continue
        if line.startswith("data: "):
            data_lines.append(line.removeprefix("data: "))

    if current_event and data_lines:
        events.append(_parse_sse_event(current_event, "\n".join(data_lines)))
    return tuple(events)


def _parse_sse_event(event_name: str, data_text: str) -> SseWireEvent:
    payload: JsonValue = json.loads(data_text)
    assert isinstance(payload, dict)
    if event_name == "state":
        run_id = payload.get("run_id")
        state = payload.get("state")
        assert isinstance(run_id, str)
        assert isinstance(state, str)
        return SseWireEvent(
            event=event_name,
            payload={"run_id": run_id, "state": state},
        )
    if event_name == "message":
        run_id = payload.get("run_id")
        text = payload.get("text")
        assert isinstance(run_id, str)
        assert isinstance(text, str)
        return SseWireEvent(event=event_name, payload={"run_id": run_id, "text": text})
    if event_name == "answer":
        run_id = payload.get("run_id")
        state = payload.get("state")
        answer = _parse_answer_body(payload.get("answer"))
        assert isinstance(run_id, str)
        assert state == RunState.COMPLETED.value
        return SseWireEvent(
            event=event_name,
            payload={
                "run_id": run_id,
                "state": "completed",
                "answer": answer,
            },
        )

    run_id = payload.get("run_id")
    state = payload.get("state")
    user_message = payload.get("user_message")
    assert isinstance(run_id, str)
    assert isinstance(state, str)
    assert isinstance(user_message, str)
    return SseWireEvent(
        event=event_name,
        payload={
            "run_id": run_id,
            "state": state,
            "user_message": user_message,
        },
    )


def fixed_recovery_now() -> datetime:
    return FIXED_CHAT_NOW


def _parse_answer_body(value: JsonValue) -> AnswerSseBody:
    assert isinstance(value, dict)
    blocks_value = value.get("blocks")
    assert isinstance(blocks_value, list)
    return {"blocks": [_parse_answer_block(block) for block in blocks_value]}


def _parse_answer_block(value: JsonValue) -> AnswerBlockSsePayload:
    assert isinstance(value, dict)
    markdown = value.get("markdown")
    assert isinstance(markdown, str)
    references_value = value.get("references")
    if references_value is None:
        return {"markdown": markdown}
    assert isinstance(references_value, list)
    return {
        "markdown": markdown,
        "references": [
            _parse_answer_reference(reference) for reference in references_value
        ],
    }


def _parse_answer_reference(value: JsonValue) -> AnswerReferenceSsePayload:
    assert isinstance(value, dict)
    source_type = value.get("source_type")
    label = value.get("label")
    url = value.get("url")
    locator_value = value.get("locator")
    assert isinstance(source_type, str)
    assert isinstance(label, str)
    assert isinstance(url, str)
    return {
        "source_type": source_type,
        "label": label,
        "url": url,
        "locator": _parse_pdf_locator(locator_value),
    }


def _parse_pdf_locator(value: JsonValue) -> PdfLocatorSsePayload:
    assert isinstance(value, dict)
    page_start = value.get("page_start")
    page_end = value.get("page_end")
    assert isinstance(page_start, int)
    assert isinstance(page_end, int)
    return {"page_start": page_start, "page_end": page_end}

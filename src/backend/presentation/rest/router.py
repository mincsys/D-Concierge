import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from typing import Literal, Protocol, TypedDict
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse

from backend.application.artifacts.get_artifact import GetArtifactUseCase
from backend.application.chat.append_chat_run import AppendChatRunUseCase
from backend.application.chat.get_chat_detail import GetChatDetailUseCase
from backend.application.chat.start_chat import StartChatUseCase
from backend.application.execution.cancel_chat_run import CancelChatRunUseCase
from backend.application.execution.execute_chat_run import RunEvent
from backend.application.history.list_chat_histories import ListChatHistoriesUseCase
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    ChatDetail,
    DisplayReferenceData,
    RunDetail,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.references.get_reference_data import GetReferenceDataUseCase
from backend.domain.execution.run_state_policy import RunState
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.presentation.schemas.api import (
    AnswerBlockResponseSchema,
    AnswerResponseSchema,
    AppConfigResponseSchema,
    CancelChatRunResponseSchema,
    ChatDetailResponseSchema,
    ChatHistoryItemResponseSchema,
    ChatRunResponseSchema,
    ChatStartRequestSchema,
    ChatStartResponseSchema,
    DisplayReferenceSchema,
    IntermediateMessageResponseSchema,
    PdfLocatorSchema,
)
from backend.presentation.sse.run_event_broker import RunEventSubscription
from backend.shared.errors import AppError, ErrorClass


class PdfLocatorPayload(TypedDict):
    """SSE回答内のPDF locator payload。"""

    page_start: int
    page_end: int


class DisplayReferencePayload(TypedDict):
    """SSE回答内の表示用参照元payload。"""

    source_type: Literal["pdf"]
    label: str
    url: str
    locator: PdfLocatorPayload


class AnswerPayload(TypedDict):
    """SSE回答表示payload。"""

    blocks: list["AnswerBlockPayload"]


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


class RunEventSource(Protocol):
    """runイベント購読境界。"""

    def subscribe(self, run_id: UUID) -> RunEventSubscription:
        """対象runのイベント購読を開始する。"""

    def unsubscribe(self, subscription: RunEventSubscription) -> None:
        """対象runのイベント購読を解除する。"""


class DisconnectableRequest(Protocol):
    """SSE接続の切断状態を確認できるリクエスト境界。"""

    async def is_disconnected(self) -> bool:
        """クライアント接続が切断済みかを返す。"""


_SSE_IDLE_POLL_INTERVAL_SECONDS = 0.1


def create_api_router(
    *,
    welcome_message: str | None,
    input_suggestions: tuple[str, ...],
    start_chat_usecase: StartChatUseCase,
    append_chat_run_usecase: AppendChatRunUseCase,
    cancel_chat_run_usecase: CancelChatRunUseCase,
    list_histories_usecase: ListChatHistoriesUseCase,
    get_chat_detail_usecase: GetChatDetailUseCase,
    get_reference_data_usecase: GetReferenceDataUseCase,
    get_artifact_usecase: GetArtifactUseCase,
    run_event_source: RunEventSource | None,
    trace_logger: TraceLogWriter,
    trace_id_factory: Callable[[], str],
) -> APIRouter:
    """チャットAPIルートを生成する。"""
    router = APIRouter()

    @router.get("/api/app-config", response_model=AppConfigResponseSchema)
    def get_app_config() -> AppConfigResponseSchema:
        trace_id = trace_id_factory()
        with _api_trace(trace_logger, trace_id, "app_config"):
            return AppConfigResponseSchema(
                welcome_message=welcome_message,
                input_suggestions=list(input_suggestions),
            )

    @router.post("/api/chats/start", response_model=ChatStartResponseSchema)
    def start_chat(request: ChatStartRequestSchema) -> ChatStartResponseSchema:
        trace_id = trace_id_factory()
        with _api_trace(trace_logger, trace_id, "start_chat"):
            accepted = start_chat_usecase.execute(
                request.user_instruction,
                trace_id=trace_id,
            )
            return _accepted_response(accepted.chat_id, accepted.run_id)

    @router.post("/api/chats/{chat_id}/runs", response_model=ChatStartResponseSchema)
    def append_chat_run(
        chat_id: UUID, request: ChatStartRequestSchema
    ) -> ChatStartResponseSchema:
        trace_id = trace_id_factory()
        with _api_trace(trace_logger, trace_id, "append_chat_run", chat_id=chat_id):
            accepted = append_chat_run_usecase.execute(
                chat_id=chat_id,
                user_instruction=request.user_instruction,
                trace_id=trace_id,
            )
            return _accepted_response(accepted.chat_id, accepted.run_id)

    @router.get(
        "/api/chat-histories",
        response_model=list[ChatHistoryItemResponseSchema],
    )
    def list_chat_histories() -> list[ChatHistoryItemResponseSchema]:
        trace_id = trace_id_factory()
        with _api_trace(trace_logger, trace_id, "chat_histories"):
            return [
                ChatHistoryItemResponseSchema(
                    chat_id=str(item.chat_id),
                    title=item.title,
                    latest_run_id=(
                        str(item.latest_run_id) if item.latest_run_id else None
                    ),
                    latest_state=item.latest_state,
                    updated_at=item.updated_at.isoformat(),
                )
                for item in list_histories_usecase.execute()
            ]

    @router.get("/api/chats/{chat_id}", response_model=ChatDetailResponseSchema)
    def get_chat_detail(chat_id: UUID) -> ChatDetailResponseSchema:
        trace_id = trace_id_factory()
        with _api_trace(trace_logger, trace_id, "chat_detail", chat_id=chat_id):
            return _chat_detail_response(get_chat_detail_usecase.execute(chat_id))

    @router.post(
        "/api/chats/{chat_id}/runs/{run_id}/cancel",
        response_model=CancelChatRunResponseSchema,
    )
    def cancel_chat_run(chat_id: UUID, run_id: UUID) -> CancelChatRunResponseSchema:
        trace_id = trace_id_factory()
        with _api_trace(
            trace_logger, trace_id, "cancel_chat_run", chat_id=chat_id, run_id=run_id
        ):
            canceled = cancel_chat_run_usecase.request_cancel(
                chat_id=chat_id,
                run_id=run_id,
                trace_id=trace_id,
            )
            return CancelChatRunResponseSchema(
                run_id=str(canceled.run_id),
                state=canceled.state,
                user_message=canceled.user_message,
            )

    @router.get("/api/chats/{chat_id}/runs/{run_id}/sse")
    async def stream_run_events(
        chat_id: UUID, run_id: UUID, request: Request
    ) -> StreamingResponse:
        trace_id = trace_id_factory()
        return StreamingResponse(
            _run_sse_events(
                get_chat_detail_usecase,
                run_event_source,
                chat_id,
                run_id,
                trace_logger,
                trace_id,
                request,
            ),
            media_type="text/event-stream",
        )

    @router.get("/api/references/{reference_id}")
    def get_reference(reference_id: UUID) -> FileResponse:
        trace_id = trace_id_factory()
        with _api_trace(trace_logger, trace_id, "reference_delivery"):
            opened = get_reference_data_usecase.execute(reference_id)
            return FileResponse(opened.path, media_type=opened.mime_type)

    @router.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: UUID) -> FileResponse:
        trace_id = trace_id_factory()
        with _api_trace(trace_logger, trace_id, "artifact_delivery"):
            opened = get_artifact_usecase.execute(artifact_id)
            return FileResponse(opened.path, media_type=opened.mime_type)

    return router


async def _run_sse_events(
    get_chat_detail_usecase: GetChatDetailUseCase,
    run_event_source: RunEventSource | None,
    chat_id: UUID,
    run_id: UUID,
    trace_logger: TraceLogWriter,
    trace_id: str,
    request: DisconnectableRequest,
) -> AsyncIterator[bytes]:
    with _api_trace(trace_logger, trace_id, "sse", chat_id=chat_id, run_id=run_id):
        if run_event_source is None:
            state, saved_messages = _run_sse_snapshot(
                get_chat_detail_usecase,
                chat_id,
                run_id,
            )
            yield _sse_event_bytes("state", _state_payload(run_id, state))
            for message in saved_messages:
                yield _sse_event_bytes(
                    "message", MessageEventPayload(run_id=str(run_id), text=message)
                )
            return

        subscription = run_event_source.subscribe(run_id)
        try:
            state, saved_messages = _run_sse_snapshot(
                get_chat_detail_usecase,
                chat_id,
                run_id,
            )
            replayed_messages = list(saved_messages)
            yield _sse_event_bytes("state", _state_payload(run_id, state))
            for message in saved_messages:
                yield _sse_event_bytes(
                    "message", MessageEventPayload(run_id=str(run_id), text=message)
                )
            while True:
                if await request.is_disconnected():
                    return
                has_event, event = subscription.poll_event()
                if not has_event:
                    await asyncio.sleep(_SSE_IDLE_POLL_INTERVAL_SECONDS)
                    continue
                if event is None:
                    return
                if _is_replayed_message_event(event, replayed_messages):
                    continue
                yield _sse_event_bytes(event.event, _run_event_payload(event))
                if event.event in {"answer", "error", "canceled"}:
                    return
        finally:
            run_event_source.unsubscribe(subscription)


def _run_sse_snapshot(
    get_chat_detail_usecase: GetChatDetailUseCase, chat_id: UUID, run_id: UUID
) -> tuple[RunState, tuple[str, ...]]:
    detail = get_chat_detail_usecase.execute(chat_id)
    for run in detail.runs:
        if run.run_id == run_id:
            return (
                run.state,
                tuple(message.text for message in run.intermediate_messages),
            )
    raise AppError(ErrorClass.NOT_FOUND, "対象のチャット実行処理が見つかりません。")


def _is_replayed_message_event(event: RunEvent, replayed_messages: list[str]) -> bool:
    if event.event != "message" or not replayed_messages:
        return False
    try:
        replayed_index = replayed_messages.index(event.text or "")
    except ValueError:
        replayed_messages.clear()
        return False
    del replayed_messages[: replayed_index + 1]
    return True


@contextmanager
def _api_trace(
    trace_logger: TraceLogWriter,
    trace_id: str,
    stage: str,
    chat_id: UUID | None = None,
    run_id: UUID | None = None,
) -> Iterator[None]:
    trace_logger.write(
        TraceLogRecord(
            trace_id=trace_id,
            event_name="api_started",
            stage=stage,
            chat_id=chat_id,
            run_id=run_id,
        )
    )
    try:
        yield
    except AppError as exc:
        trace_logger.write(
            TraceLogRecord(
                trace_id=trace_id,
                event_name="api_failed",
                stage=stage,
                chat_id=chat_id,
                run_id=run_id,
                error_class=exc.error_class.value,
                exception_type=type(exc).__name__,
                message=exc.user_message,
            )
        )
        raise
    except Exception as exc:
        trace_logger.write(
            TraceLogRecord(
                trace_id=trace_id,
                event_name="api_failed",
                stage=stage,
                chat_id=chat_id,
                run_id=run_id,
                error_class=ErrorClass.SYSTEM.value,
                exception_type=type(exc).__name__,
                message=str(exc),
            )
        )
        raise
    else:
        trace_logger.write(
            TraceLogRecord(
                trace_id=trace_id,
                event_name="api_finished",
                stage=stage,
                chat_id=chat_id,
                run_id=run_id,
            )
        )


def _sse_event_bytes(event_name: str, payload: SsePayload) -> bytes:
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {payload_json}\n\n".encode()


def _run_event_payload(event: RunEvent) -> SsePayload:
    match event.event:
        case "state":
            return _state_payload(event.run_id, _required_state(event))
        case "message":
            return MessageEventPayload(run_id=str(event.run_id), text=event.text or "")
        case "answer":
            if event.answer is None:
                raise AppError(ErrorClass.SYSTEM, "回答イベントの内容が不正です。")
            return AnswerEventPayload(
                run_id=str(event.run_id),
                state=_required_state(event),
                answer=_answer_payload(event.answer),
            )
        case "error" | "canceled":
            return EndEventPayload(
                run_id=str(event.run_id),
                state=_required_state(event),
                user_message=event.user_message or "",
            )


def _state_payload(run_id: UUID, state: str) -> StateEventPayload:
    return StateEventPayload(run_id=str(run_id), state=state)


def _required_state(event: RunEvent) -> str:
    if event.state is None:
        raise AppError(ErrorClass.SYSTEM, "状態イベントの内容が不正です。")
    return event.state


def _answer_payload(answer: AnswerData) -> AnswerPayload:
    return AnswerPayload(
        blocks=[
            AnswerBlockPayload(
                markdown=block.markdown,
                references=[
                    DisplayReferencePayload(
                        source_type="pdf",
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


def _accepted_response(chat_id: UUID, run_id: UUID) -> ChatStartResponseSchema:
    return ChatStartResponseSchema(
        chat_id=str(chat_id),
        run_id=str(run_id),
        sse_url=f"/api/chats/{chat_id}/runs/{run_id}/sse",
        state="受付",
    )


def _chat_detail_response(detail: ChatDetail) -> ChatDetailResponseSchema:
    return ChatDetailResponseSchema(
        chat_id=str(detail.chat_id),
        title=detail.title,
        runs=[_run_response(run) for run in detail.runs],
    )


def _run_response(run: RunDetail) -> ChatRunResponseSchema:
    return ChatRunResponseSchema(
        run_id=str(run.run_id),
        state=run.state,
        user_instruction=run.user_instruction,
        intermediate_messages=[
            IntermediateMessageResponseSchema(text=message.text)
            for message in run.intermediate_messages
        ],
        answer=_answer_response(run.answer) if run.answer is not None else None,
        user_message=run.user_message,
    )


def _answer_response(answer: AnswerData) -> AnswerResponseSchema:
    return AnswerResponseSchema(
        blocks=[_answer_block_response(block) for block in answer.blocks],
    )


def _answer_block_response(block: AnswerBlockData) -> AnswerBlockResponseSchema:
    return AnswerBlockResponseSchema(
        markdown=block.markdown,
        references=[_reference_response(reference) for reference in block.references],
    )


def _reference_response(reference: DisplayReferenceData) -> DisplayReferenceSchema:
    return DisplayReferenceSchema(
        source_type="pdf",
        label=reference.label,
        url=f"/api/references/{reference.reference_id}",
        locator=PdfLocatorSchema(
            page_start=reference.page_start,
            page_end=reference.page_end,
        ),
    )

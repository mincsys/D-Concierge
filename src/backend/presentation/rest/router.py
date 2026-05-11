import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Protocol, TypedDict
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse

from backend.application.artifacts.get_artifact import GetArtifactUseCase
from backend.application.chat.append_chat_run import AppendChatRunUseCase
from backend.application.chat.get_chat_detail import GetChatDetailUseCase
from backend.application.chat.start_chat import StartChatUseCase
from backend.application.execution.cancel_chat_run import CancelChatRunUseCase
from backend.application.execution.execute_chat_run import RunEvent
from backend.application.execution.run_event_type import RunEventType
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
from backend.domain.execution.run_state import RunState
from backend.domain.references.source_type import SourceType
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.presentation.rest.trace_context import (
    ensure_request_trace_context,
    request_trace_id,
)
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
from backend.shared.error_class import ErrorClass
from backend.shared.errors import AppError
from backend.shared.tracing.exception import exception_message, exception_stacktrace


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
    def get_app_config(request: Request) -> AppConfigResponseSchema:
        _set_request_trace(request, trace_id_factory, stage="app_config")
        return AppConfigResponseSchema(
            welcome_message=welcome_message,
            input_suggestions=list(input_suggestions),
        )

    @router.post("/api/chats/start", response_model=ChatStartResponseSchema)
    def start_chat(
        body: ChatStartRequestSchema, request: Request
    ) -> ChatStartResponseSchema:
        trace_id = _set_request_trace(request, trace_id_factory, stage="start_chat")
        accepted = start_chat_usecase.execute(
            body.user_instruction,
            trace_id=trace_id,
        )
        context = ensure_request_trace_context(request)
        context.chat_id = accepted.chat_id
        context.run_id = accepted.run_id
        return _accepted_response(accepted.chat_id, accepted.run_id)

    @router.post("/api/chats/{chat_id}/runs", response_model=ChatStartResponseSchema)
    def append_chat_run(
        chat_id: UUID, body: ChatStartRequestSchema, request: Request
    ) -> ChatStartResponseSchema:
        trace_id = _set_request_trace(
            request, trace_id_factory, stage="append_chat_run", chat_id=chat_id
        )
        accepted = append_chat_run_usecase.execute(
            chat_id=chat_id,
            user_instruction=body.user_instruction,
            trace_id=trace_id,
        )
        ensure_request_trace_context(request).run_id = accepted.run_id
        return _accepted_response(accepted.chat_id, accepted.run_id)

    @router.get(
        "/api/chat-histories",
        response_model=list[ChatHistoryItemResponseSchema],
    )
    def list_chat_histories(request: Request) -> list[ChatHistoryItemResponseSchema]:
        _set_request_trace(request, trace_id_factory, stage="chat_histories")
        return [
            ChatHistoryItemResponseSchema(
                chat_id=str(item.chat_id),
                title=item.title,
                latest_run_id=(str(item.latest_run_id) if item.latest_run_id else None),
                latest_state=item.latest_state.value,
                updated_at=item.updated_at.isoformat(),
            )
            for item in list_histories_usecase.execute()
        ]

    @router.get("/api/chats/{chat_id}", response_model=ChatDetailResponseSchema)
    def get_chat_detail(chat_id: UUID, request: Request) -> ChatDetailResponseSchema:
        _set_request_trace(
            request, trace_id_factory, stage="chat_detail", chat_id=chat_id
        )
        return _chat_detail_response(get_chat_detail_usecase.execute(chat_id))

    @router.post(
        "/api/chats/{chat_id}/runs/{run_id}/cancel",
        response_model=CancelChatRunResponseSchema,
    )
    def cancel_chat_run(
        chat_id: UUID, run_id: UUID, request: Request
    ) -> CancelChatRunResponseSchema:
        trace_id = _set_request_trace(
            request,
            trace_id_factory,
            stage="cancel_chat_run",
            chat_id=chat_id,
            run_id=run_id,
        )
        canceled = cancel_chat_run_usecase.request_cancel(
            chat_id=chat_id,
            run_id=run_id,
            trace_id=trace_id,
        )
        return CancelChatRunResponseSchema(
            run_id=str(canceled.run_id),
            state=canceled.state.value,
            user_message=canceled.user_message,
        )

    @router.get("/api/chats/{chat_id}/runs/{run_id}/sse")
    async def stream_run_events(
        chat_id: UUID, run_id: UUID, request: Request
    ) -> StreamingResponse:
        trace_id = _set_request_trace(
            request, trace_id_factory, stage="sse", chat_id=chat_id, run_id=run_id
        )
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
    def get_reference(reference_id: UUID, request: Request) -> FileResponse:
        _set_request_trace(
            request,
            trace_id_factory,
            stage="reference_delivery",
            reference_id=reference_id,
        )
        opened = get_reference_data_usecase.execute(reference_id)
        return FileResponse(opened.path, media_type=opened.mime_type)

    @router.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: UUID, request: Request) -> FileResponse:
        _set_request_trace(
            request,
            trace_id_factory,
            stage="artifact_delivery",
            artifact_id=artifact_id,
        )
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
    try:
        if run_event_source is None:
            state, saved_messages = _run_sse_snapshot(
                get_chat_detail_usecase,
                chat_id,
                run_id,
            )
            yield _sse_event_bytes(
                RunEventType.STATE.value,
                _state_payload(run_id, state),
            )
            for message in saved_messages:
                yield _sse_event_bytes(
                    RunEventType.MESSAGE.value,
                    MessageEventPayload(run_id=str(run_id), text=message),
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
            yield _sse_event_bytes(
                RunEventType.STATE.value,
                _state_payload(run_id, state),
            )
            for message in saved_messages:
                yield _sse_event_bytes(
                    RunEventType.MESSAGE.value,
                    MessageEventPayload(run_id=str(run_id), text=message),
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
                yield _sse_event_bytes(event.event.value, _run_event_payload(event))
                if event.event in {
                    RunEventType.ANSWER,
                    RunEventType.ERROR,
                    RunEventType.CANCELED,
                }:
                    return
        finally:
            run_event_source.unsubscribe(subscription)
    except AppError as exc:
        _write_sse_failure_trace(
            trace_logger=trace_logger,
            trace_id=trace_id,
            chat_id=chat_id,
            run_id=run_id,
            exc=exc,
            error_class=exc.error_class.value,
            user_message=exc.user_message,
        )
        yield _sse_event_bytes(
            RunEventType.ERROR.value,
            EndEventPayload(
                run_id=str(run_id),
                state=RunState.ERROR.value,
                user_message=exc.user_message,
            ),
        )
    except Exception as exc:
        _write_sse_failure_trace(
            trace_logger=trace_logger,
            trace_id=trace_id,
            chat_id=chat_id,
            run_id=run_id,
            exc=exc,
            error_class=ErrorClass.SYSTEM.value,
            user_message="処理中にエラーが発生しました。",
        )
        yield _sse_event_bytes(
            RunEventType.ERROR.value,
            EndEventPayload(
                run_id=str(run_id),
                state=RunState.ERROR.value,
                user_message="処理中にエラーが発生しました。",
            ),
        )


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
    if event.event is not RunEventType.MESSAGE or not replayed_messages:
        return False
    try:
        replayed_index = replayed_messages.index(event.text or "")
    except ValueError:
        replayed_messages.clear()
        return False
    del replayed_messages[: replayed_index + 1]
    return True


def _set_request_trace(
    request: Request,
    trace_id_factory: Callable[[], str],
    stage: str,
    chat_id: UUID | None = None,
    run_id: UUID | None = None,
    reference_id: UUID | None = None,
    artifact_id: UUID | None = None,
) -> str:
    trace_id = request_trace_id(request, trace_id_factory())
    context = ensure_request_trace_context(request)
    context.stage = stage
    context.chat_id = chat_id
    context.run_id = run_id
    context.reference_id = reference_id
    context.artifact_id = artifact_id
    return trace_id


def _write_sse_failure_trace(
    trace_logger: TraceLogWriter,
    trace_id: str,
    chat_id: UUID,
    run_id: UUID,
    exc: Exception,
    error_class: str,
    user_message: str,
) -> None:
    trace_logger.write(
        TraceLogRecord(
            trace_id=trace_id,
            event_name="sse_failed",
            stage="sse",
            chat_id=chat_id,
            run_id=run_id,
            error_class=error_class,
            exception_type=type(exc).__name__,
            run_state=RunState.ERROR.value,
            stacktrace=exception_stacktrace(exc),
            message=(
                user_message if isinstance(exc, AppError) else exception_message(exc)
            ),
        )
    )


def _sse_event_bytes(event_name: str, payload: SsePayload) -> bytes:
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {payload_json}\n\n".encode()


def _run_event_payload(event: RunEvent) -> SsePayload:
    match event.event:
        case RunEventType.STATE:
            return _state_payload(event.run_id, _required_state(event))
        case RunEventType.MESSAGE:
            return MessageEventPayload(run_id=str(event.run_id), text=event.text or "")
        case RunEventType.ANSWER:
            if event.answer is None:
                raise AppError(ErrorClass.SYSTEM, "回答イベントの内容が不正です。")
            return AnswerEventPayload(
                run_id=str(event.run_id),
                state=_required_state(event).value,
                answer=_answer_payload(event.answer),
            )
        case RunEventType.ERROR | RunEventType.CANCELED:
            return EndEventPayload(
                run_id=str(event.run_id),
                state=_required_state(event).value,
                user_message=event.user_message or "",
            )


def _state_payload(run_id: UUID, state: RunState) -> StateEventPayload:
    return StateEventPayload(run_id=str(run_id), state=state.value)


def _required_state(event: RunEvent) -> RunState:
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
                        source_type=SourceType.PDF.value,
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
        state=RunState.ACCEPTED.value,
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
        state=run.state.value,
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
        source_type=SourceType.PDF.value,
        label=reference.label,
        url=f"/api/references/{reference.reference_id}",
        locator=PdfLocatorSchema(
            page_start=reference.page_start,
            page_end=reference.page_end,
        ),
    )

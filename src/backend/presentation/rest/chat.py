from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, NotRequired, TypedDict
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.application.chat.append_chat_run import (
    AppendChatRunCommand,
    AppendChatRunUseCase,
)
from backend.application.chat.delete_chat import DeleteChatCommand, DeleteChatUseCase
from backend.application.chat.dto import (
    AnswerBlockResult,
    AnswerResult,
    ChatAcceptedResult,
    ChatDetailResult,
    ChatRunResult,
    DisplayReferenceResult,
    HistoryItemResult,
    IntermediateMessageResult,
)
from backend.application.chat.get_chat_detail import (
    GetChatDetailCommand,
    GetChatDetailUseCase,
)
from backend.application.chat.interfaces import RunExecutionDispatcherLike
from backend.application.chat.start_chat import StartChatCommand, StartChatUseCase
from backend.application.execution.cancel_chat_run import (
    CancelChatRunCommand,
    CancelChatRunUseCase,
)
from backend.application.execution.run_event_broker import (
    RunEvent,
    RunEventBroker,
    RunEventType,
)
from backend.application.history.list_chat_histories import (
    ListChatHistoriesCommand,
    ListChatHistoriesUseCase,
)
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    DisplayReferenceData,
    IntermediateMessageData,
    SseRunSnapshot,
)
from backend.domain.execution.run_state import RunState
from backend.infrastructure.database.repositories.chat import SqlAlchemyChatRepository
from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)
from backend.infrastructure.runtime.clock import SystemClock
from backend.infrastructure.runtime.run_execution_dispatcher import (
    NoopCodexRunCancellation,
    NullRunExecutionDispatcher,
)
from backend.infrastructure.runtime.uuid_generator import UuidGenerator
from backend.presentation.errors.http import trace_id_from_request
from backend.presentation.rest.dependencies import (
    AuthenticatedUser,
    get_authenticated_user,
    get_session_factory,
    get_settings,
)
from backend.presentation.schemas.chat import (
    AnswerBlockResponse,
    AnswerResponse,
    CancelChatRunResponse,
    ChatAcceptedResponse,
    ChatDetailResponse,
    ChatHistoryItemResponse,
    ChatInstructionRequest,
    ChatRunResponse,
    DeleteChatResponse,
    DisplayReferenceResponse,
    IntermediateMessageResponse,
    PdfLocatorResponse,
)
from backend.presentation.sse.payload import (
    AnswerBlockPayload,
    AnswerEventPayload,
    AnswerPayload,
    ReferencePayload,
    format_sse_data,
    format_sse_event,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

router = APIRouter()


@router.post("/api/chats/start", response_model=ChatAcceptedResponse)
async def start_chat(
    request: Request,
    body: ChatInstructionRequest,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> ChatAcceptedResponse:
    """新規チャット開始を受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = StartChatUseCase(
            repository=SqlAlchemyChatRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            dispatcher=_run_execution_dispatcher(request),
            id_generator=UuidGenerator(),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            StartChatCommand(
                authenticated_user_id=authenticated_user.user_id,
                user_instruction=body.user_instruction,
                trace_id=trace_id_from_request(request),
            )
        )
    return _accepted_response(result)


@router.delete(
    "/api/chats/{chat_id}",
    response_model=DeleteChatResponse,
    status_code=202,
)
async def delete_chat(
    request: Request,
    chat_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> DeleteChatResponse:
    """チャット削除を受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = DeleteChatUseCase(
            repository=SqlAlchemyChatRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            dispatcher=request.app.state.chat_deletion_dispatcher,
            trace_logger=request.app.state.trace_log_writer,
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            DeleteChatCommand(
                authenticated_user_id=authenticated_user.user_id,
                chat_id=chat_id,
                trace_id=trace_id_from_request(request),
            )
        )
    return DeleteChatResponse(
        chat_id=str(result.chat_id),
        chat_state=result.chat_state,
    )


@router.post("/api/chats/{chat_id}/runs", response_model=ChatAcceptedResponse)
async def append_chat_run(
    request: Request,
    chat_id: UUID,
    body: ChatInstructionRequest,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> ChatAcceptedResponse:
    """継続指示を受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = AppendChatRunUseCase(
            repository=SqlAlchemyChatRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            dispatcher=_run_execution_dispatcher(request),
            id_generator=UuidGenerator(),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            AppendChatRunCommand(
                authenticated_user_id=authenticated_user.user_id,
                chat_id=chat_id,
                user_instruction=body.user_instruction,
                trace_id=trace_id_from_request(request),
            )
        )
    return _accepted_response(result)


@router.get("/api/chats/{chat_id}/runs/{run_id}/sse")
async def subscribe_run_events(
    request: Request,
    chat_id: UUID,
    run_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> StreamingResponse:
    """runの現在状態、保存済みイベント、ライブイベントをSSE形式で配信する。"""

    session_factory = get_session_factory(request)
    with session_factory() as session:
        repository = SqlAlchemyChatRepository(session)
        snapshot = repository.get_run_state_for_sse(
            authenticated_user.user_id,
            chat_id,
            run_id,
        )
        if snapshot is None:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="対象runが見つかりません。",
            )
        messages = repository.list_intermediate_messages_for_sse(run_id)

    broker = _run_event_broker(request)
    return StreamingResponse(
        _run_event_stream(
            request=request,
            broker=broker,
            run_id=run_id,
            initial_events=_initial_sse_events(run_id, snapshot, messages),
            initial_terminal=_is_terminal_snapshot(snapshot.state),
        ),
        media_type="text/event-stream",
    )


def _initial_sse_events(
    run_id: UUID,
    snapshot: SseRunSnapshot,
    messages: tuple[IntermediateMessageData, ...],
) -> tuple[str, ...]:
    events = [
        format_sse_data(
            "state",
            {"run_id": str(run_id), "state": snapshot.state},
        )
    ]
    events.extend(
        format_sse_data("message", {"run_id": str(run_id), "text": message.text})
        for message in messages
    )
    if snapshot.state == RunState.COMPLETED.value and snapshot.answer is not None:
        events.append(
            format_sse_data(
                "answer",
                _answer_event_payload(run_id, snapshot.answer),
            )
        )
    elif snapshot.state in _ERROR_END_STATES and snapshot.user_message is not None:
        events.append(
            format_sse_data(
                _terminal_event_name(snapshot.state),
                {
                    "run_id": str(run_id),
                    "state": snapshot.state,
                    "user_message": snapshot.user_message,
                },
            )
        )
    return tuple(events)


async def _run_event_stream(
    *,
    request: Request,
    broker: RunEventBroker,
    run_id: UUID,
    initial_events: tuple[str, ...],
    initial_terminal: bool,
) -> AsyncIterator[str]:
    subscription = broker.subscribe(run_id)
    try:
        for event_text in initial_events:
            yield event_text
        if initial_terminal:
            return
        while True:
            if await request.is_disconnected():
                return
            event = subscription.poll_event()
            if event is None:
                await asyncio.sleep(0.05)
                continue
            yield format_sse_event(event)
            if event.event_type in _TERMINAL_RUN_EVENT_TYPES:
                return
    finally:
        broker.unsubscribe(subscription)


def _is_terminal_snapshot(state: str) -> bool:
    return state == RunState.COMPLETED.value or state in _ERROR_END_STATES


def _run_event_broker(request: Request) -> RunEventBroker:
    broker = request.app.state.run_event_broker
    if not isinstance(broker, RunEventBroker):
        raise AppError(
            error_type=ErrorType.CONFIGURATION,
            trace=True,
            diagnostic_message="SSEイベント配信境界が初期化されていません。",
        )
    return broker


def _run_execution_dispatcher(request: Request) -> RunExecutionDispatcherLike:
    dispatcher = getattr(request.app.state, "run_execution_dispatcher", None)
    if dispatcher is None:
        return NullRunExecutionDispatcher()
    if not isinstance(dispatcher, RunExecutionDispatcherLike):
        raise AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="run実行dispatcherが初期化されていません。",
        )
    return dispatcher


class _BrokerRunEventPublisher:
    """キャンセル受付結果をRunEventBrokerへ配信する境界。"""

    def __init__(self, broker: RunEventBroker) -> None:
        self._broker = broker

    def publish(
        self,
        run_id: UUID,
        event_name: str,
        payload_state: str,
        user_message: str | None = None,
    ) -> None:
        if event_name == "state":
            self._broker.publish(RunEvent.state(run_id=run_id, state=payload_state))
            return
        if event_name == "canceled" and user_message is not None:
            self._broker.publish(
                RunEvent.end(
                    event_type=RunEventType.CANCELED,
                    run_id=run_id,
                    state=payload_state,
                    user_message=user_message,
                )
            )


_TERMINAL_RUN_EVENT_TYPES = frozenset(
    {RunEventType.ANSWER, RunEventType.ERROR, RunEventType.CANCELED}
)


def _answer_event_payload(run_id: UUID, answer: AnswerData) -> AnswerEventPayload:
    return {
        "run_id": str(run_id),
        "state": RunState.COMPLETED.value,
        "answer": _answer_payload(answer),
    }


def _answer_payload(answer: AnswerData) -> AnswerPayload:
    return {
        "blocks": [_answer_block_payload(block) for block in answer.blocks],
    }


def _answer_block_payload(block: AnswerBlockData) -> AnswerBlockPayload:
    return {
        "markdown": block.markdown,
        "references": [_reference_payload(reference) for reference in block.references],
    }


def _reference_payload(reference: DisplayReferenceData) -> ReferencePayload:
    return {
        "source_type": reference.source_type,
        "label": reference.label,
        "url": f"/api/references/{reference.reference_id}",
        "locator": {
            "page_start": reference.page_start,
            "page_end": reference.page_end,
        },
    }


def _terminal_event_name(state: str) -> str:
    if state == RunState.CANCELED.value:
        return "canceled"
    return "error"


@router.post(
    "/api/chats/{chat_id}/runs/{run_id}/cancel",
    response_model=CancelChatRunResponse,
)
async def cancel_chat_run(
    request: Request,
    chat_id: UUID,
    run_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> CancelChatRunResponse:
    """チャットrunのキャンセルを受け付ける。"""

    settings = await get_settings(request)
    session_factory = get_session_factory(request)
    broker = _run_event_broker(request)
    with session_factory() as session:
        use_case = CancelChatRunUseCase(
            repository=SqlAlchemyChatRepository(session),
            transaction_manager=SqlAlchemyTransactionManager(session),
            codex_runner=NoopCodexRunCancellation(),
            event_publisher=_BrokerRunEventPublisher(broker),
            clock=SystemClock(settings.app.timezone),
        )
        result = use_case.execute(
            CancelChatRunCommand(
                authenticated_user_id=authenticated_user.user_id,
                chat_id=chat_id,
                run_id=run_id,
                trace_id=trace_id_from_request(request),
            )
        )
    return CancelChatRunResponse(
        state=result.state,
        user_message=result.user_message,
    )


@router.get("/api/chat-histories", response_model=list[ChatHistoryItemResponse])
async def list_chat_histories(
    request: Request,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> list[ChatHistoryItemResponse]:
    """履歴一覧を取得する。"""

    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = ListChatHistoriesUseCase(
            repository=SqlAlchemyChatRepository(session),
        )
        result = use_case.execute(
            ListChatHistoriesCommand(
                authenticated_user_id=authenticated_user.user_id,
                trace_id=trace_id_from_request(request),
            )
        )
    return [_history_item_response(item) for item in result.items]


@router.get(
    "/api/chats/{chat_id}",
    response_model=None,
)
async def get_chat_detail(
    request: Request,
    chat_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> ChatDetailPayload:
    """履歴詳細を取得する。"""

    session_factory = get_session_factory(request)
    with session_factory() as session:
        use_case = GetChatDetailUseCase(
            repository=SqlAlchemyChatRepository(session),
        )
        result = use_case.execute(
            GetChatDetailCommand(
                authenticated_user_id=authenticated_user.user_id,
                chat_id=chat_id,
                trace_id=trace_id_from_request(request),
            )
        )
    return _chat_detail_payload(result)


class IntermediateMessagePayload(TypedDict):
    text: str


class PdfLocatorPayload(TypedDict):
    page_start: int
    page_end: int


class DisplayReferencePayload(TypedDict):
    source_type: str
    label: str
    url: str
    locator: PdfLocatorPayload


class AnswerBlockResponsePayload(TypedDict):
    markdown: str
    references: list[DisplayReferencePayload]


class AnswerResponsePayload(TypedDict):
    blocks: list[AnswerBlockResponsePayload]


class ChatRunPayload(TypedDict):
    run_id: str
    state: str
    user_instruction: str
    intermediate_messages: list[IntermediateMessagePayload]
    answer: NotRequired[AnswerResponsePayload | None]
    user_message: NotRequired[str]


class ChatDetailPayload(TypedDict):
    chat_id: str
    title: str
    runs: list[ChatRunPayload]


def _accepted_response(result: ChatAcceptedResult) -> ChatAcceptedResponse:
    return ChatAcceptedResponse(
        chat_id=str(result.chat_id),
        run_id=str(result.run_id),
        sse_url=result.sse_url,
        state=result.state,
    )


def _history_item_response(item: HistoryItemResult) -> ChatHistoryItemResponse:
    return ChatHistoryItemResponse(
        chat_id=str(item.chat_id),
        title=item.title,
        latest_run_id=(
            str(item.latest_run_id) if item.latest_run_id is not None else None
        ),
        latest_state=item.latest_state,
        updated_at=item.updated_at.isoformat(),
    )


def _chat_detail_response(result: ChatDetailResult) -> ChatDetailResponse:
    return ChatDetailResponse(
        chat_id=str(result.chat_id),
        title=result.title,
        runs=tuple(_chat_run_response(run) for run in result.runs),
    )


def _chat_detail_payload(result: ChatDetailResult) -> ChatDetailPayload:
    return {
        "chat_id": str(result.chat_id),
        "title": result.title,
        "runs": [_chat_run_payload(run) for run in result.runs],
    }


def _chat_run_payload(run: ChatRunResult) -> ChatRunPayload:
    payload: ChatRunPayload = {
        "run_id": str(run.run_id),
        "state": run.state,
        "user_instruction": run.user_instruction,
        "intermediate_messages": [
            {"text": message.text} for message in run.intermediate_messages
        ],
    }
    if run.answer is not None:
        payload["answer"] = _answer_payload_for_rest(run.answer)
    elif run.state in _ERROR_END_STATES:
        payload["answer"] = None
    if run.user_message is not None:
        payload["user_message"] = run.user_message
    return payload


def _answer_payload_for_rest(answer: AnswerResult) -> AnswerResponsePayload:
    return {
        "blocks": [_answer_block_payload_for_rest(block) for block in answer.blocks],
    }


def _answer_block_payload_for_rest(
    block: AnswerBlockResult,
) -> AnswerBlockResponsePayload:
    return {
        "markdown": block.markdown,
        "references": [
            _display_reference_payload(reference) for reference in block.references
        ],
    }


def _display_reference_payload(
    reference: DisplayReferenceResult,
) -> DisplayReferencePayload:
    return {
        "source_type": reference.source_type,
        "label": reference.label,
        "url": reference.url,
        "locator": {
            "page_start": reference.locator.page_start,
            "page_end": reference.locator.page_end,
        },
    }


def _chat_run_response(run: ChatRunResult) -> ChatRunResponse:
    return ChatRunResponse(
        run_id=str(run.run_id),
        state=run.state,
        user_instruction=run.user_instruction,
        intermediate_messages=tuple(
            _intermediate_message_response(message)
            for message in run.intermediate_messages
        ),
        answer=_answer_response(run.answer),
        user_message=run.user_message,
    )


def _intermediate_message_response(
    message: IntermediateMessageResult,
) -> IntermediateMessageResponse:
    return IntermediateMessageResponse(text=message.text)


def _answer_response(answer: AnswerResult | None) -> AnswerResponse | None:
    if answer is None:
        return None
    return AnswerResponse(
        blocks=tuple(_answer_block_response(block) for block in answer.blocks),
    )


def _answer_block_response(block: AnswerBlockResult) -> AnswerBlockResponse:
    return AnswerBlockResponse(
        markdown=block.markdown,
        references=tuple(
            _display_reference_response(reference) for reference in block.references
        ),
    )


def _display_reference_response(
    reference: DisplayReferenceResult,
) -> DisplayReferenceResponse:
    return DisplayReferenceResponse(
        source_type=reference.source_type,
        label=reference.label,
        url=reference.url,
        locator=PdfLocatorResponse(
            page_start=reference.locator.page_start,
            page_end=reference.locator.page_end,
        ),
    )


_ERROR_END_STATES = frozenset(
    {
        RunState.CANCELED.value,
        RunState.ERROR.value,
        RunState.TIMED_OUT.value,
    }
)

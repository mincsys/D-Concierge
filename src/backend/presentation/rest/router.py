import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from backend.application.account.authenticate_session import AuthenticateSessionUseCase
from backend.application.account.change_password import ChangePasswordUseCase
from backend.application.account.change_user_name import ChangeUserNameUseCase
from backend.application.account.delete_account import DeleteAccountUseCase
from backend.application.account.login import LoginUseCase
from backend.application.account.logout import LogoutUseCase
from backend.application.account.register_account import RegisterAccountUseCase
from backend.application.artifacts.get_artifact import GetArtifactUseCase
from backend.application.chat.acceptance import AcceptedChatRunResult
from backend.application.chat.append_chat_run import AppendChatRunUseCase
from backend.application.chat.delete_chat import DeleteChatUseCase
from backend.application.chat.get_chat_detail import GetChatDetailUseCase
from backend.application.chat.start_chat import StartChatUseCase
from backend.application.execution.cancel_chat_run import CancelChatRunUseCase
from backend.application.execution.execute_chat_run import RunEvent
from backend.application.execution.run_event_type import RunEventType
from backend.application.history.list_chat_histories import ListChatHistoriesUseCase
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    AuthenticatedUser,
    ChatDetail,
    DisplayReferenceData,
    RunDetail,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.ports.trace_log.interface import TraceLoggerPort
from backend.application.references.get_reference_data import GetReferenceDataUseCase
from backend.domain.execution.run_state import RunState
from backend.presentation.errors.http import user_message_for_error
from backend.presentation.rest.trace_context import (
    ensure_request_trace_context,
    request_trace_id,
)
from backend.presentation.schemas.api import (
    AnswerBlockResponseSchema,
    AnswerResponseSchema,
    AppConfigResponseSchema,
    AuthUserResponseSchema,
    CancelChatRunResponseSchema,
    ChangePasswordRequestSchema,
    ChangeUserNameRequestSchema,
    ChatDetailResponseSchema,
    ChatHistoryItemResponseSchema,
    ChatRunResponseSchema,
    ChatStartRequestSchema,
    ChatStartResponseSchema,
    CurrentUserResponseSchema,
    DeleteAccountResponseSchema,
    DeleteChatResponseSchema,
    DisplayReferenceSchema,
    IntermediateMessageResponseSchema,
    LoginRequestSchema,
    PdfLocatorSchema,
    RegisterAccountRequestSchema,
)
from backend.presentation.sse.payload import (
    end_payload,
    message_payload,
    run_event_payload,
    sse_event_bytes,
    state_payload,
)
from backend.presentation.sse.run_event_broker import RunEventSubscription
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError, ChatRunNotFoundError
from backend.shared.tracing.exception import exception_message, exception_stacktrace
from backend.shared.user_messages import UNEXPECTED_FAILURE_MESSAGE


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
_SESSION_COOKIE_NAME = "d_concierge_session"
_SESSION_COOKIE_MAX_AGE_SECONDS = 400 * 24 * 60 * 60


def create_api_router(
    *,
    welcome_message: str | None,
    input_suggestions: tuple[str, ...],
    start_chat_usecase: StartChatUseCase,
    append_chat_run_usecase: AppendChatRunUseCase,
    cancel_chat_run_usecase: CancelChatRunUseCase,
    delete_chat_usecase: DeleteChatUseCase,
    list_histories_usecase: ListChatHistoriesUseCase,
    get_chat_detail_usecase: GetChatDetailUseCase,
    get_reference_data_usecase: GetReferenceDataUseCase,
    get_artifact_usecase: GetArtifactUseCase,
    run_event_source: RunEventSource | None,
    trace_logger: TraceLoggerPort,
    trace_id_factory: Callable[[], str],
    authenticate_session_usecase: AuthenticateSessionUseCase,
    register_account_usecase: RegisterAccountUseCase,
    login_usecase: LoginUseCase,
    logout_usecase: LogoutUseCase,
    change_user_name_usecase: ChangeUserNameUseCase,
    change_password_usecase: ChangePasswordUseCase,
    delete_account_usecase: DeleteAccountUseCase,
) -> APIRouter:
    """チャットAPIルートを生成する。"""
    router = APIRouter()

    @router.get("/api/app-config", response_model=AppConfigResponseSchema)
    def get_app_config(request: Request) -> AppConfigResponseSchema:
        _set_request_trace(request, trace_id_factory, stage="app_config")
        _authenticated_user(request, authenticate_session_usecase)
        return AppConfigResponseSchema(
            welcome_message=welcome_message,
            input_suggestions=list(input_suggestions),
        )

    @router.get("/api/auth/me", response_model=CurrentUserResponseSchema)
    def get_current_user(request: Request) -> CurrentUserResponseSchema:
        _set_request_trace(request, trace_id_factory, stage="auth_me")
        user = _authenticated_user(request, authenticate_session_usecase)
        return _current_user_response(user)

    @router.post("/api/auth/register", response_model=CurrentUserResponseSchema)
    def register_account(
        body: RegisterAccountRequestSchema, request: Request, response: Response
    ) -> CurrentUserResponseSchema:
        trace_id = _set_request_trace(
            request, trace_id_factory, stage="account_register"
        )
        result = register_account_usecase.execute(
            user_id=body.user_id,
            user_name=body.user_name,
            password=body.password,
            password_confirmation=body.password_confirmation,
            existing_session_token=_session_token(request),
            trace_id=trace_id,
        )
        _set_session_cookie(response, result.session_token)
        return _current_user_response(result.user)

    @router.post("/api/auth/login", response_model=CurrentUserResponseSchema)
    def login(
        body: LoginRequestSchema, request: Request, response: Response
    ) -> CurrentUserResponseSchema:
        trace_id = _set_request_trace(request, trace_id_factory, stage="login")
        result = login_usecase.execute(
            body.user_id,
            body.password,
            _session_token(request),
            trace_id,
        )
        _set_session_cookie(response, result.session_token)
        return _current_user_response(result.user)

    @router.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response) -> None:
        trace_id = _set_request_trace(request, trace_id_factory, stage="logout")
        logout_usecase.execute(_session_token(request), trace_id=trace_id)
        _delete_session_cookie(response)

    @router.patch("/api/account/name", response_model=CurrentUserResponseSchema)
    def change_user_name(
        body: ChangeUserNameRequestSchema, request: Request
    ) -> CurrentUserResponseSchema:
        trace_id = _set_request_trace(
            request, trace_id_factory, stage="change_user_name"
        )
        user = _authenticated_user(request, authenticate_session_usecase)
        changed = change_user_name_usecase.execute(
            user.user_id, body.user_name, trace_id=trace_id
        )
        return _current_user_response(changed)

    @router.patch("/api/account/password", status_code=204)
    def change_password(
        body: ChangePasswordRequestSchema, request: Request, response: Response
    ) -> None:
        _ = response
        trace_id = _set_request_trace(
            request, trace_id_factory, stage="change_password"
        )
        user = _authenticated_user(request, authenticate_session_usecase)
        change_password_usecase.execute(
            user.user_id,
            body.current_password,
            body.new_password,
            body.new_password_confirmation,
            trace_id=trace_id,
        )

    @router.delete(
        "/api/account",
        response_model=DeleteAccountResponseSchema,
        status_code=202,
    )
    def delete_account(
        request: Request, response: Response
    ) -> DeleteAccountResponseSchema:
        trace_id = _set_request_trace(request, trace_id_factory, stage="delete_account")
        user = _authenticated_user(request, authenticate_session_usecase)
        accepted = delete_account_usecase.execute(user.user_id, trace_id=trace_id)
        _delete_session_cookie(response)
        return DeleteAccountResponseSchema(account_state=accepted.account_state.value)

    @router.post("/api/chats/start", response_model=ChatStartResponseSchema)
    def start_chat(
        body: ChatStartRequestSchema, request: Request
    ) -> ChatStartResponseSchema:
        trace_id = _set_request_trace(request, trace_id_factory, stage="start_chat")
        user = _authenticated_user(request, authenticate_session_usecase)
        accepted = start_chat_usecase.execute(
            user_instruction=body.user_instruction,
            trace_id=trace_id,
            user_id=user.user_id,
        )
        context = ensure_request_trace_context(request)
        context.chat_id = accepted.chat_id
        context.run_id = accepted.run_id
        return _accepted_response(accepted)

    @router.post("/api/chats/{chat_id}/runs", response_model=ChatStartResponseSchema)
    def append_chat_run(
        chat_id: UUID, body: ChatStartRequestSchema, request: Request
    ) -> ChatStartResponseSchema:
        trace_id = _set_request_trace(
            request, trace_id_factory, stage="append_chat_run", chat_id=chat_id
        )
        user = _authenticated_user(request, authenticate_session_usecase)
        accepted = append_chat_run_usecase.execute(
            user_id=user.user_id,
            chat_id=chat_id,
            user_instruction=body.user_instruction,
            trace_id=trace_id,
        )
        ensure_request_trace_context(request).run_id = accepted.run_id
        return _accepted_response(accepted)

    @router.get(
        "/api/chat-histories",
        response_model=list[ChatHistoryItemResponseSchema],
    )
    def list_chat_histories(request: Request) -> list[ChatHistoryItemResponseSchema]:
        _set_request_trace(request, trace_id_factory, stage="chat_histories")
        user = _authenticated_user(request, authenticate_session_usecase)
        return [
            ChatHistoryItemResponseSchema(
                chat_id=str(item.chat_id),
                title=item.title,
                latest_run_id=(str(item.latest_run_id) if item.latest_run_id else None),
                latest_state=item.latest_state.value,
                updated_at=item.updated_at.isoformat(),
            )
            for item in list_histories_usecase.execute(user.user_id)
        ]

    @router.get("/api/chats/{chat_id}", response_model=ChatDetailResponseSchema)
    def get_chat_detail(chat_id: UUID, request: Request) -> ChatDetailResponseSchema:
        _set_request_trace(
            request, trace_id_factory, stage="chat_detail", chat_id=chat_id
        )
        user = _authenticated_user(request, authenticate_session_usecase)
        return _chat_detail_response(
            get_chat_detail_usecase.execute(chat_id, user_id=user.user_id)
        )

    @router.delete(
        "/api/chats/{chat_id}",
        response_model=DeleteChatResponseSchema,
        status_code=202,
    )
    def delete_chat(chat_id: UUID, request: Request) -> DeleteChatResponseSchema:
        trace_id = _set_request_trace(
            request, trace_id_factory, stage="delete_chat", chat_id=chat_id
        )
        user = _authenticated_user(request, authenticate_session_usecase)
        deleted = delete_chat_usecase.execute(
            chat_id=chat_id, trace_id=trace_id, user_id=user.user_id
        )
        return DeleteChatResponseSchema(
            chat_id=str(deleted.chat_id),
            chat_state=deleted.chat_state.value,
        )

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
        user = _authenticated_user(request, authenticate_session_usecase)
        get_chat_detail_usecase.execute(chat_id, user_id=user.user_id)
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
        user = _authenticated_user(request, authenticate_session_usecase)
        get_chat_detail_usecase.execute(chat_id, user_id=user.user_id)
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
        user = _authenticated_user(request, authenticate_session_usecase)
        opened = get_reference_data_usecase.execute(reference_id, user_id=user.user_id)
        return FileResponse(opened.path, media_type=opened.mime_type)

    @router.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: UUID, request: Request) -> FileResponse:
        _set_request_trace(
            request,
            trace_id_factory,
            stage="artifact_delivery",
            artifact_id=artifact_id,
        )
        user = _authenticated_user(request, authenticate_session_usecase)
        opened = get_artifact_usecase.execute(artifact_id, user_id=user.user_id)
        return FileResponse(opened.path, media_type=opened.mime_type)

    return router


async def _run_sse_events(
    get_chat_detail_usecase: GetChatDetailUseCase,
    run_event_source: RunEventSource | None,
    chat_id: UUID,
    run_id: UUID,
    trace_logger: TraceLoggerPort,
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
            yield sse_event_bytes(
                RunEventType.STATE.value,
                state_payload(run_id, state),
            )
            for message in saved_messages:
                yield sse_event_bytes(
                    RunEventType.MESSAGE.value,
                    message_payload(run_id, message),
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
            yield sse_event_bytes(
                RunEventType.STATE.value,
                state_payload(run_id, state),
            )
            for message in saved_messages:
                yield sse_event_bytes(
                    RunEventType.MESSAGE.value,
                    message_payload(run_id, message),
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
                yield sse_event_bytes(event.event.value, run_event_payload(event))
                if event.event in {
                    RunEventType.ANSWER,
                    RunEventType.ERROR,
                    RunEventType.CANCELED,
                }:
                    return
        finally:
            run_event_source.unsubscribe(subscription)
    except AppError as exc:
        user_message = user_message_for_error(exc)
        if exc.trace:
            _write_sse_failure_trace(
                trace_logger=trace_logger,
                trace_id=trace_id,
                chat_id=chat_id,
                run_id=run_id,
                exc=exc,
                error_type=exc.error_type.value,
                message=exc.diagnostic_message,
            )
        yield sse_event_bytes(
            RunEventType.ERROR.value,
            end_payload(run_id, RunState.ERROR.value, user_message),
        )
    except Exception as exc:
        _write_sse_failure_trace(
            trace_logger=trace_logger,
            trace_id=trace_id,
            chat_id=chat_id,
            run_id=run_id,
            exc=exc,
            error_type=ErrorType.SYSTEM.value,
            message=exception_message(exc),
        )
        yield sse_event_bytes(
            RunEventType.ERROR.value,
            end_payload(
                run_id,
                RunState.ERROR.value,
                UNEXPECTED_FAILURE_MESSAGE,
            ),
        )


def _run_sse_snapshot(
    get_chat_detail_usecase: GetChatDetailUseCase, chat_id: UUID, run_id: UUID
) -> tuple[str, tuple[str, ...]]:
    detail = get_chat_detail_usecase.execute(chat_id)
    for run in detail.runs:
        if run.run_id == run_id:
            return (
                run.state.value,
                tuple(message.text for message in run.intermediate_messages),
            )
    raise ChatRunNotFoundError()


def _session_token(request: Request) -> str | None:
    return request.cookies.get(_SESSION_COOKIE_NAME)


def _authenticated_user(
    request: Request,
    authenticate_session_usecase: AuthenticateSessionUseCase,
) -> AuthenticatedUser:
    return authenticate_session_usecase.execute(
        _session_token(request),
        trace_id=request_trace_id(request, "unavailable"),
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=token,
        max_age=_SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(key=_SESSION_COOKIE_NAME, path="/")


def _current_user_response(user: AuthenticatedUser) -> CurrentUserResponseSchema:
    return CurrentUserResponseSchema(
        user=AuthUserResponseSchema(
            user_id=user.user_id,
            user_name=user.user_name,
        )
    )


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
    trace_logger: TraceLoggerPort,
    trace_id: str,
    chat_id: UUID,
    run_id: UUID,
    exc: Exception,
    error_type: str,
    message: str,
) -> None:
    trace_logger.write(
        TraceLogRecord(
            trace_id=trace_id,
            event_name="sse_failed",
            stage="sse",
            chat_id=chat_id,
            run_id=run_id,
            error_type=error_type,
            exception_type=type(exc).__name__,
            run_state=RunState.ERROR.value,
            stacktrace=exception_stacktrace(exc),
            message=message,
        )
    )


def _accepted_response(accepted: AcceptedChatRunResult) -> ChatStartResponseSchema:
    return ChatStartResponseSchema(
        chat_id=str(accepted.chat_id),
        run_id=str(accepted.run_id),
        sse_url=accepted.sse_url,
        state=accepted.state.value,
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
        source_type=reference.source_type.value,
        label=reference.label,
        url=f"/api/references/{reference.reference_id}",
        locator=PdfLocatorSchema(
            page_start=reference.page_start,
            page_end=reference.page_end,
        ),
    )

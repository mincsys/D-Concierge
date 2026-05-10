import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, Protocol, TypedDict
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.application.artifacts.save_adopted_artifacts import (
    SaveAdoptedArtifactsUseCase,
)
from backend.application.chat.append_chat_run import AppendChatRunUseCase
from backend.application.chat.start_chat import StartChatUseCase
from backend.application.execution.cancel_chat_run import CancelChatRunUseCase
from backend.application.execution.execute_chat_run import (
    ExecuteChatRunUseCase,
    RunEvent,
)
from backend.application.execution.recover_unfinished_runs import (
    RecoverUnfinishedRunsUseCase,
)
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    ChatDetail,
    DisplayReferenceData,
    RunDetail,
)
from backend.application.ports.database.interface import ChatRepositoryPort
from backend.application.ports.runtime.interface import (
    BackgroundExecutorPort,
    RunExecutionDispatcherPort,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.validation.validate_answer import ValidateAnswerUseCase
from backend.domain.execution.run_state_policy import RunState
from backend.infrastructure.codex.cancel_requester import CodexCancelRequester
from backend.infrastructure.codex.codex_runner import (
    CancelResult,
    CodexRunner,
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.generation_runner import (
    CodexGenerationRunnerAdapter,
)
from backend.infrastructure.codex.reference_validator import CodexReferenceValidator
from backend.infrastructure.codex.session_workdir import CodexSessionWorkdirResolver
from backend.infrastructure.config.loader import ConfigLoader
from backend.infrastructure.config.models import AppConfig
from backend.infrastructure.database.repositories.sqlalchemy_chat_repository import (
    SqlAlchemyChatRepository,
)
from backend.infrastructure.filesystem.artifacts.file_artifact_store import (
    FileArtifactStore,
)
from backend.infrastructure.filesystem.path_security import PathSecurityService
from backend.infrastructure.runtime.run_execution_dispatcher import (
    InProcessRunExecutionDispatcher,
)
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.presentation.schemas import (
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
    ErrorResponseSchema,
    IntermediateMessageResponseSchema,
    PdfLocatorSchema,
)
from backend.presentation.sse.run_event_broker import (
    RunEventBroker,
    RunEventSubscription,
)
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


class ApplicationCodexRunner(Protocol):
    """MVP既定実行構成が利用するCodexRunner境界。"""

    def run_generation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """生成用codex execを実行する。"""

    def run_validation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """検証用codex execを実行する。"""

    def cancel(self, run_id: UUID, trace_id: str) -> CancelResult:
        """実行中codex execへ終了要求を送る。"""


class _DefaultRunDispatcher:
    """create_app省略時にMVP既定実行構成を使うためのsentinel。"""


_DEFAULT_RUN_DISPATCHER = _DefaultRunDispatcher()
_SSE_IDLE_POLL_INTERVAL_SECONDS = 0.1


def create_app(
    config: AppConfig | None = None,
    repository: ChatRepositoryPort | None = None,
    run_dispatcher: RunExecutionDispatcherPort | None | _DefaultRunDispatcher = (
        _DEFAULT_RUN_DISPATCHER
    ),
    run_event_source: RunEventSource | None = None,
    codex_runner: ApplicationCodexRunner | None = None,
    background_executor: BackgroundExecutorPort | None = None,
) -> FastAPI:
    """D-ConciergeのFastAPIアプリを生成する。"""
    app_config = (
        config if config is not None else ConfigLoader.load(Path("config.yaml"))
    )
    chat_repository: ChatRepositoryPort = (
        repository
        if repository is not None
        else _create_sqlalchemy_repository(app_config)
    )
    trace_logger = TraceLogWriter(app_config.trace_log.dir)
    (
        runtime_run_dispatcher,
        runtime_run_event_source,
        cancel_requester,
        cancel_event_publisher,
    ) = _create_runtime_services(
        app_config=app_config,
        chat_repository=chat_repository,
        run_dispatcher=run_dispatcher,
        run_event_source=run_event_source,
        codex_runner=codex_runner,
        background_executor=background_executor,
        trace_logger=trace_logger,
    )
    start_chat_usecase = StartChatUseCase(
        repository=chat_repository,
        run_dispatcher=runtime_run_dispatcher,
    )
    append_chat_run_usecase = AppendChatRunUseCase(
        repository=chat_repository,
        run_dispatcher=runtime_run_dispatcher,
    )
    cancel_chat_run_usecase = CancelChatRunUseCase(
        repository=chat_repository,
        cancel_requester=cancel_requester,
        event_publisher=cancel_event_publisher,
    )
    if runtime_run_dispatcher is not None:
        RecoverUnfinishedRunsUseCase(
            repository=chat_repository,
            run_dispatcher=runtime_run_dispatcher,
        ).execute(trace_id=_new_trace_id())
    app = FastAPI(title="D-Concierge")

    @app.exception_handler(AppError)
    async def handle_app_error(_request: object, exc: AppError) -> JSONResponse:
        status_code = _status_code(exc.error_class)
        payload = ErrorResponseSchema(
            error=exc.error_class.value,
            message=exc.user_message,
        )
        return JSONResponse(
            status_code=status_code,
            content={"error": payload.error, "message": payload.message},
        )

    @app.get("/api/app-config", response_model=AppConfigResponseSchema)
    def get_app_config() -> AppConfigResponseSchema:
        trace_id = _new_trace_id()
        with _api_trace(trace_logger, trace_id, "app_config"):
            return AppConfigResponseSchema(
                welcome_message=app_config.ui.welcome_message,
                input_suggestions=list(app_config.ui.input_suggestions),
            )

    @app.post("/api/chats/start", response_model=ChatStartResponseSchema)
    def start_chat(request: ChatStartRequestSchema) -> ChatStartResponseSchema:
        trace_id = _new_trace_id()
        with _api_trace(trace_logger, trace_id, "start_chat"):
            accepted = start_chat_usecase.execute(
                request.user_instruction,
                trace_id=trace_id,
            )
            return _accepted_response(accepted.chat_id, accepted.run_id)

    @app.post("/api/chats/{chat_id}/runs", response_model=ChatStartResponseSchema)
    def append_chat_run(
        chat_id: UUID, request: ChatStartRequestSchema
    ) -> ChatStartResponseSchema:
        trace_id = _new_trace_id()
        with _api_trace(trace_logger, trace_id, "append_chat_run", chat_id=chat_id):
            accepted = append_chat_run_usecase.execute(
                chat_id=chat_id,
                user_instruction=request.user_instruction,
                trace_id=trace_id,
            )
            return _accepted_response(accepted.chat_id, accepted.run_id)

    @app.get("/api/chat-histories", response_model=list[ChatHistoryItemResponseSchema])
    def list_chat_histories() -> list[ChatHistoryItemResponseSchema]:
        trace_id = _new_trace_id()
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
                for item in chat_repository.list_histories()
            ]

    @app.get("/api/chats/{chat_id}", response_model=ChatDetailResponseSchema)
    def get_chat_detail(chat_id: UUID) -> ChatDetailResponseSchema:
        trace_id = _new_trace_id()
        with _api_trace(trace_logger, trace_id, "chat_detail", chat_id=chat_id):
            return _chat_detail_response(chat_repository.get_chat_detail(chat_id))

    @app.post(
        "/api/chats/{chat_id}/runs/{run_id}/cancel",
        response_model=CancelChatRunResponseSchema,
    )
    def cancel_chat_run(chat_id: UUID, run_id: UUID) -> CancelChatRunResponseSchema:
        trace_id = _new_trace_id()
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

    @app.get("/api/chats/{chat_id}/runs/{run_id}/sse")
    async def stream_run_events(
        chat_id: UUID, run_id: UUID, request: Request
    ) -> StreamingResponse:
        trace_id = _new_trace_id()
        return StreamingResponse(
            _run_sse_events(
                chat_repository,
                runtime_run_event_source,
                chat_id,
                run_id,
                trace_logger,
                trace_id,
                request,
            ),
            media_type="text/event-stream",
        )

    @app.get("/api/references/{reference_id}")
    def get_reference(reference_id: UUID) -> FileResponse:
        trace_id = _new_trace_id()
        with _api_trace(trace_logger, trace_id, "reference_delivery"):
            reference = chat_repository.get_reference(reference_id)
            if reference.source_type != "pdf":
                raise AppError(ErrorClass.FORBIDDEN, "対象の参照元は表示できません。")
            path = PathSecurityService.resolve_file(
                root=app_config.datasource_dir,
                relative_path=reference.relative_path,
                allowed_suffixes=(".pdf",),
            )
            if not path.exists():
                raise AppError(ErrorClass.NOT_FOUND, "対象の参照元が見つかりません。")
            return FileResponse(path, media_type="application/pdf")

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: UUID) -> FileResponse:
        trace_id = _new_trace_id()
        with _api_trace(trace_logger, trace_id, "artifact_delivery"):
            artifact = chat_repository.get_artifact(artifact_id)
            if artifact.mime_type not in {
                "image/svg+xml",
                "image/png",
                "text/html",
                "text/csv",
            }:
                raise AppError(ErrorClass.FORBIDDEN, "対象の成果物は表示できません。")
            path = PathSecurityService.resolve_file(
                root=app_config.codex.saved_artifacts_dir,
                relative_path=artifact.relative_path,
                allowed_suffixes=(".svg", ".png", ".html", ".csv"),
            )
            if not path.exists():
                raise AppError(ErrorClass.NOT_FOUND, "対象の成果物が見つかりません。")
            return FileResponse(path, media_type=artifact.mime_type)

    return app


def _create_runtime_services(
    app_config: AppConfig,
    chat_repository: ChatRepositoryPort,
    run_dispatcher: RunExecutionDispatcherPort | None | _DefaultRunDispatcher,
    run_event_source: RunEventSource | None,
    codex_runner: ApplicationCodexRunner | None,
    background_executor: BackgroundExecutorPort | None,
    trace_logger: TraceLogWriter,
) -> tuple[
    RunExecutionDispatcherPort | None,
    RunEventSource | None,
    CodexCancelRequester | None,
    RunEventBroker | None,
]:
    if not isinstance(run_dispatcher, _DefaultRunDispatcher):
        return run_dispatcher, run_event_source, None, None

    event_broker = RunEventBroker()
    runtime_codex_runner = codex_runner if codex_runner is not None else CodexRunner()
    generation_runner = CodexGenerationRunnerAdapter(
        repository=chat_repository,
        codex_runner=runtime_codex_runner,
        codex_config=app_config.codex,
        datasource_dir=app_config.datasource_dir,
        timeout_seconds=app_config.server.timeout_seconds,
    )
    reference_validator = CodexReferenceValidator(
        repository=chat_repository,
        codex_runner=runtime_codex_runner,
        validator_config=app_config.validator.codex,
        datasource_dir=app_config.datasource_dir,
        timeout_seconds=app_config.server.timeout_seconds,
    )
    answer_validator = ValidateAnswerUseCase(
        reference_validator=reference_validator,
        max_retries=app_config.validator.max_retries,
    )
    artifact_saver = SaveAdoptedArtifactsUseCase(
        artifact_store=FileArtifactStore(app_config.codex.saved_artifacts_dir)
    )
    execute_usecase = ExecuteChatRunUseCase(
        repository=chat_repository,
        codex_runner=generation_runner,
        answer_validator=answer_validator,
        event_publisher=event_broker,
        artifact_saver=artifact_saver,
        session_workdir_resolver=CodexSessionWorkdirResolver(
            repository=chat_repository,
            base_workdir=app_config.codex.workdir,
        ),
        trace_logger=trace_logger,
        timeout_seconds=app_config.server.timeout_seconds,
    )
    return (
        InProcessRunExecutionDispatcher(
            run_executor=execute_usecase,
            background_executor=background_executor,
        ),
        run_event_source if run_event_source is not None else event_broker,
        CodexCancelRequester(runtime_codex_runner),
        event_broker,
    )


async def _run_sse_events(
    chat_repository: ChatRepositoryPort,
    run_event_source: RunEventSource | None,
    chat_id: UUID,
    run_id: UUID,
    trace_logger: TraceLogWriter,
    trace_id: str,
    request: DisconnectableRequest,
) -> AsyncIterator[bytes]:
    with _api_trace(trace_logger, trace_id, "sse", chat_id=chat_id, run_id=run_id):
        if run_event_source is None:
            state, saved_messages = _run_sse_snapshot(chat_repository, chat_id, run_id)
            yield _sse_event_bytes("state", _state_payload(run_id, state))
            for message in saved_messages:
                yield _sse_event_bytes(
                    "message", MessageEventPayload(run_id=str(run_id), text=message)
                )
            return

        subscription = run_event_source.subscribe(run_id)
        try:
            state, saved_messages = _run_sse_snapshot(chat_repository, chat_id, run_id)
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
    chat_repository: ChatRepositoryPort, chat_id: UUID, run_id: UUID
) -> tuple[RunState, tuple[str, ...]]:
    detail = chat_repository.get_chat_detail(chat_id)
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


def _new_trace_id() -> str:
    return str(uuid4())


def _create_sqlalchemy_repository(config: AppConfig) -> SqlAlchemyChatRepository:
    engine = create_engine(config.database.url)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    return SqlAlchemyChatRepository(session_factory=session_factory)


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


def _status_code(error_class: ErrorClass) -> int:
    match error_class:
        case ErrorClass.INPUT | ErrorClass.CONFIGURATION:
            return 400
        case ErrorClass.NOT_FOUND:
            return 404
        case ErrorClass.CONFLICT:
            return 409
        case ErrorClass.FORBIDDEN:
            return 403
        case ErrorClass.SYSTEM:
            return 500

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from backend.app.router.registration import register_api_router
from backend.app.static.spa import mount_spa_static_files
from backend.application.artifacts.get_artifact import GetArtifactUseCase
from backend.application.artifacts.save_adopted_artifacts import (
    SaveAdoptedArtifactsUseCase,
)
from backend.application.chat.append_chat_run import AppendChatRunUseCase
from backend.application.chat.delete_chat import DeleteChatUseCase
from backend.application.chat.execute_chat_deletion import (
    ExecuteChatDeletionUseCase,
)
from backend.application.chat.get_chat_detail import GetChatDetailUseCase
from backend.application.chat.start_chat import StartChatUseCase
from backend.application.execution.cancel_chat_run import CancelChatRunUseCase
from backend.application.execution.execute_chat_run import ExecuteChatRunUseCase
from backend.application.execution.recover_unfinished_runs import (
    RecoverUnfinishedRunsUseCase,
)
from backend.application.history.list_chat_histories import ListChatHistoriesUseCase
from backend.application.ports.database.interface import (
    ChatRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import (
    BackgroundExecutorPort,
    ChatDeletionDispatcherPort,
    ClockPort,
    IdGeneratorPort,
    RunExecutionDispatcherPort,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.references.get_reference_data import GetReferenceDataUseCase
from backend.application.transactions import NoopTransactionManager
from backend.application.validation.validate_answer import ValidateAnswerUseCase
from backend.infrastructure.codex.cancel_requester import CodexCancelRequester
from backend.infrastructure.codex.codex_runner import (
    CancelResult,
    CodexRunner,
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.generation_runner import CodexGenerationRunnerAdapter
from backend.infrastructure.codex.reference_validator import (
    CodexReferenceFileValidator,
    CodexValidationRunnerAdapter,
)
from backend.infrastructure.codex.session_workdir import CodexSessionWorkdirResolver
from backend.infrastructure.codex.session_workdir_cleanup import (
    CodexSessionWorkdirCleanup,
)
from backend.infrastructure.config.loader import ConfigLoader
from backend.infrastructure.config.models import AppConfig
from backend.infrastructure.database.repositories.sqlalchemy_chat_repository import (
    SqlAlchemyChatRepository,
)
from backend.infrastructure.database.session.factory import create_transaction_manager
from backend.infrastructure.filesystem.artifacts.file_artifact_store import (
    FileArtifactStore,
)
from backend.infrastructure.filesystem.references.file_reference_store import (
    FileReferenceStore,
)
from backend.infrastructure.runtime.chat_deletion_dispatcher import (
    InProcessChatDeletionDispatcher,
)
from backend.infrastructure.runtime.run_execution_dispatcher import (
    InProcessRunExecutionDispatcher,
)
from backend.infrastructure.runtime.system_clock import SystemClock
from backend.infrastructure.runtime.uuid_generator import UuidGenerator
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.presentation.errors.http import (
    error_response_payload,
    status_code,
    user_message_for_error,
)
from backend.presentation.rest.router import RunEventSource, create_api_router
from backend.presentation.rest.trace_context import (
    RequestTraceContext,
    ensure_request_trace_context,
    request_trace_id,
)
from backend.presentation.sse.run_event_broker import RunEventBroker
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.exception import exception_message, exception_stacktrace
from backend.shared.user_messages import (
    REQUEST_VALIDATION_FAILURE_MESSAGE,
    UNEXPECTED_FAILURE_MESSAGE,
)


class ApplicationCodexRunner(Protocol):
    """既定実行構成が利用するCodexRunner境界。"""

    def run_generation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """生成用codex execを実行する。"""

    def run_validation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """検証用codex execを実行する。"""

    def cancel(self, run_id: UUID, trace_id: str) -> CancelResult:
        """実行中codex execへ終了要求を送る。"""


class _DefaultRunDispatcher:
    """create_app省略時に既定実行構成を使うためのsentinel。"""


_DEFAULT_RUN_DISPATCHER = _DefaultRunDispatcher()


def create_app(
    config: AppConfig | None = None,
    repository: ChatRepositoryPort | None = None,
    run_dispatcher: RunExecutionDispatcherPort | None | _DefaultRunDispatcher = (
        _DEFAULT_RUN_DISPATCHER
    ),
    run_event_source: RunEventSource | None = None,
    codex_runner: ApplicationCodexRunner | None = None,
    background_executor: BackgroundExecutorPort | None = None,
    transaction_manager: TransactionManagerPort | None = None,
    clock: ClockPort | None = None,
    id_generator: IdGeneratorPort | None = None,
) -> FastAPI:
    """D-ConciergeのFastAPIアプリを生成する。"""
    app_config = (
        config if config is not None else ConfigLoader.load(Path("config.yaml"))
    )
    runtime_clock = clock if clock is not None else SystemClock(app_config.app.timezone)
    runtime_id_generator = id_generator if id_generator is not None else UuidGenerator()
    runtime_transaction_manager: TransactionManagerPort
    if repository is None:
        sql_transaction_manager = create_transaction_manager(app_config.database.url)
        chat_repository: ChatRepositoryPort = SqlAlchemyChatRepository(
            session_provider=sql_transaction_manager,
            clock=runtime_clock,
            id_generator=runtime_id_generator,
        )
        runtime_transaction_manager = sql_transaction_manager
    else:
        chat_repository = repository
        runtime_transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    trace_logger = TraceLogWriter(
        app_config.trace_log.dir,
        retention_days=app_config.trace_log.retention_days,
        max_files_per_day=app_config.trace_log.max_files_per_day,
        clock=runtime_clock.now_app_timezone,
    )
    trace_logger.cleanup_expired()
    (
        runtime_run_dispatcher,
        runtime_run_event_source,
        cancel_requester,
        cancel_event_publisher,
        chat_deletion_dispatcher,
    ) = _create_runtime_services(
        app_config=app_config,
        chat_repository=chat_repository,
        run_dispatcher=run_dispatcher,
        run_event_source=run_event_source,
        codex_runner=codex_runner,
        background_executor=background_executor,
        trace_logger=trace_logger,
        transaction_manager=runtime_transaction_manager,
        clock=runtime_clock,
        id_generator=runtime_id_generator,
    )

    start_chat_usecase = StartChatUseCase(
        repository=chat_repository,
        run_dispatcher=runtime_run_dispatcher,
        transaction_manager=runtime_transaction_manager,
    )
    append_chat_run_usecase = AppendChatRunUseCase(
        repository=chat_repository,
        run_dispatcher=runtime_run_dispatcher,
        transaction_manager=runtime_transaction_manager,
    )
    cancel_chat_run_usecase = CancelChatRunUseCase(
        repository=chat_repository,
        cancel_requester=cancel_requester,
        event_publisher=cancel_event_publisher,
        transaction_manager=runtime_transaction_manager,
    )
    delete_chat_usecase = DeleteChatUseCase(
        repository=chat_repository,
        deletion_dispatcher=chat_deletion_dispatcher,
        transaction_manager=runtime_transaction_manager,
        trace_logger=trace_logger,
    )
    list_histories_usecase = ListChatHistoriesUseCase(
        repository=chat_repository,
        transaction_manager=runtime_transaction_manager,
    )
    get_chat_detail_usecase = GetChatDetailUseCase(
        repository=chat_repository,
        transaction_manager=runtime_transaction_manager,
    )
    get_reference_data_usecase = GetReferenceDataUseCase(
        repository=chat_repository,
        reference_store=FileReferenceStore(app_config.datasource_dir),
        transaction_manager=runtime_transaction_manager,
    )
    get_artifact_usecase = GetArtifactUseCase(
        repository=chat_repository,
        artifact_store=FileArtifactStore(app_config.generator.saved_artifacts_dir),
        transaction_manager=runtime_transaction_manager,
    )

    if runtime_run_dispatcher is not None:
        RecoverUnfinishedRunsUseCase(
            repository=chat_repository,
            run_dispatcher=runtime_run_dispatcher,
            transaction_manager=runtime_transaction_manager,
            trace_logger=trace_logger,
        ).execute(trace_id=_new_trace_id(runtime_id_generator))
    if chat_deletion_dispatcher is not None:
        with runtime_transaction_manager.transaction():
            deleting_chat_ids = chat_repository.list_deleting_chats_for_recovery()
        for deleting_chat_id in deleting_chat_ids:
            chat_deletion_dispatcher.register(
                deleting_chat_id,
                _new_trace_id(runtime_id_generator),
            )

    app = FastAPI(title="D-Concierge")
    _register_trace_context_middleware(app, runtime_id_generator)
    _register_error_handlers(app, trace_logger)
    register_api_router(
        app,
        create_api_router(
            welcome_message=app_config.ui.welcome_message,
            input_suggestions=app_config.ui.input_suggestions,
            start_chat_usecase=start_chat_usecase,
            append_chat_run_usecase=append_chat_run_usecase,
            cancel_chat_run_usecase=cancel_chat_run_usecase,
            delete_chat_usecase=delete_chat_usecase,
            list_histories_usecase=list_histories_usecase,
            get_chat_detail_usecase=get_chat_detail_usecase,
            get_reference_data_usecase=get_reference_data_usecase,
            get_artifact_usecase=get_artifact_usecase,
            run_event_source=runtime_run_event_source,
            trace_logger=trace_logger,
            trace_id_factory=lambda: _new_trace_id(runtime_id_generator),
        ),
    )
    mount_spa_static_files(app, Path(__file__).parent / "static" / "dist")
    return app


def _create_runtime_services(
    app_config: AppConfig,
    chat_repository: ChatRepositoryPort,
    run_dispatcher: RunExecutionDispatcherPort | None | _DefaultRunDispatcher,
    run_event_source: RunEventSource | None,
    codex_runner: ApplicationCodexRunner | None,
    background_executor: BackgroundExecutorPort | None,
    trace_logger: TraceLogWriter,
    transaction_manager: TransactionManagerPort,
    clock: ClockPort,
    id_generator: IdGeneratorPort,
) -> tuple[
    RunExecutionDispatcherPort | None,
    RunEventSource | None,
    CodexCancelRequester | None,
    RunEventBroker | None,
    ChatDeletionDispatcherPort | None,
]:
    if not isinstance(run_dispatcher, _DefaultRunDispatcher):
        return run_dispatcher, run_event_source, None, None, None

    event_broker = RunEventBroker()
    runtime_codex_runner = codex_runner if codex_runner is not None else CodexRunner()
    generation_runner = CodexGenerationRunnerAdapter(
        repository=chat_repository,
        codex_runner=runtime_codex_runner,
        generator_config=app_config.generator,
        datasource_dir=app_config.datasource_dir,
        timeout_seconds=app_config.server.timeout_seconds,
        transaction_manager=transaction_manager,
    )
    reference_file_validator = CodexReferenceFileValidator(
        datasource_dir=app_config.datasource_dir,
    )
    validator_codex_runner = CodexValidationRunnerAdapter(
        repository=chat_repository,
        codex_runner=runtime_codex_runner,
        validator_config=app_config.validator,
        datasource_dir=app_config.datasource_dir,
        timeout_seconds=app_config.server.timeout_seconds,
        transaction_manager=transaction_manager,
    )
    answer_validator = ValidateAnswerUseCase(
        max_retries=app_config.generator.max_retries,
        reference_file_validator=reference_file_validator,
        validator_codex_runner=validator_codex_runner,
        validator_max_retries=app_config.validator.max_retries,
    )
    artifact_store = FileArtifactStore(app_config.generator.saved_artifacts_dir)
    artifact_saver = SaveAdoptedArtifactsUseCase(
        artifact_store=artifact_store,
        id_generator=id_generator,
    )
    execute_usecase = ExecuteChatRunUseCase(
        repository=chat_repository,
        codex_runner=generation_runner,
        answer_validator=answer_validator,
        event_publisher=event_broker,
        artifact_saver=artifact_saver,
        session_workdir_resolver=CodexSessionWorkdirResolver(
            repository=chat_repository,
            base_workdir=app_config.generator.workdir,
        ),
        trace_logger=trace_logger,
        timeout_seconds=app_config.server.timeout_seconds,
        transaction_manager=transaction_manager,
        clock=clock,
        id_generator=id_generator,
    )
    deletion_usecase = ExecuteChatDeletionUseCase(
        repository=chat_repository,
        cancel_requester=CodexCancelRequester(runtime_codex_runner),
        session_workdir_cleanup=CodexSessionWorkdirCleanup(
            generation_workdir=app_config.generator.workdir,
            validation_workdir=app_config.validator.workdir,
        ),
        artifact_deletion=artifact_store,
        transaction_manager=transaction_manager,
        trace_logger=trace_logger,
    )
    return (
        InProcessRunExecutionDispatcher(
            run_executor=execute_usecase,
            background_executor=background_executor,
        ),
        run_event_source if run_event_source is not None else event_broker,
        CodexCancelRequester(runtime_codex_runner),
        event_broker,
        InProcessChatDeletionDispatcher(
            deletion_executor=deletion_usecase,
            background_executor=background_executor,
        ),
    )


def _register_trace_context_middleware(
    app: FastAPI,
    id_generator: IdGeneratorPort,
) -> None:
    @app.middleware("http")
    async def attach_trace_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.trace_id = _new_trace_id(id_generator)
        request.state.trace_context = RequestTraceContext()
        return await call_next(request)


def _register_error_handlers(app: FastAPI, trace_logger: TraceLogWriter) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        http_status = status_code(exc.error_type)
        user_message = user_message_for_error(exc)
        if exc.trace:
            _write_api_failure_trace(
                trace_logger=trace_logger,
                request=request,
                exc=exc,
                event_name="api_failed",
                error_type=exc.error_type.value,
                status=http_status,
                message=exc.diagnostic_message,
            )
        payload = error_response_payload(exc.error_type, user_message)
        return JSONResponse(
            status_code=http_status,
            content=payload.model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        _ = trace_logger, request, exc
        payload = error_response_payload(
            ErrorType.INPUT,
            REQUEST_VALIDATION_FAILURE_MESSAGE,
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        _write_api_failure_trace(
            trace_logger=trace_logger,
            request=request,
            exc=exc,
            event_name="api_failed",
            error_type=ErrorType.SYSTEM.value,
            status=500,
            message=exception_message(exc),
        )
        payload = error_response_payload(
            ErrorType.SYSTEM,
            UNEXPECTED_FAILURE_MESSAGE,
        )
        return JSONResponse(status_code=500, content=payload.model_dump())


def _write_api_failure_trace(
    trace_logger: TraceLogWriter,
    request: Request,
    exc: Exception,
    event_name: str,
    error_type: str,
    status: int,
    message: str,
    request_validation_errors: str | None = None,
) -> None:
    context = ensure_request_trace_context(request)
    client = request.client.host if request.client is not None else None
    trace_logger.write(
        TraceLogRecord(
            trace_id=request_trace_id(request, "unavailable"),
            event_name=event_name,
            stage=_request_stage(request, context),
            chat_id=context.chat_id,
            run_id=context.run_id,
            reference_id=context.reference_id,
            artifact_id=context.artifact_id,
            error_type=error_type,
            exception_type=type(exc).__name__,
            stacktrace=exception_stacktrace(exc),
            http_method=request.method,
            path=request.url.path,
            status_code=status,
            client=client,
            request_validation_errors=request_validation_errors,
            message=message,
        )
    )


def _request_stage(request: Request, context: RequestTraceContext) -> str:
    if context.stage != "api":
        return context.stage
    endpoint = request.scope.get("endpoint")
    endpoint_name = getattr(endpoint, "__name__", None)
    if isinstance(endpoint_name, str):
        return endpoint_name
    return "api"


def _new_trace_id(id_generator: IdGeneratorPort) -> str:
    return str(id_generator.new_uuid())

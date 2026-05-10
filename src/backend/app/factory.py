from pathlib import Path
from typing import Protocol
from uuid import UUID

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.app.router.registration import register_api_router
from backend.app.static.spa import mount_spa_static_files
from backend.application.artifacts.get_artifact import GetArtifactUseCase
from backend.application.artifacts.save_adopted_artifacts import (
    SaveAdoptedArtifactsUseCase,
)
from backend.application.chat.append_chat_run import AppendChatRunUseCase
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
    ClockPort,
    IdGeneratorPort,
    RunExecutionDispatcherPort,
)
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
from backend.infrastructure.codex.reference_validator import CodexReferenceValidator
from backend.infrastructure.codex.session_workdir import CodexSessionWorkdirResolver
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
from backend.infrastructure.runtime.run_execution_dispatcher import (
    InProcessRunExecutionDispatcher,
)
from backend.infrastructure.runtime.system_clock import SystemClock
from backend.infrastructure.runtime.uuid_generator import UuidGenerator
from backend.infrastructure.trace_log.trace_log_writer import TraceLogWriter
from backend.presentation.errors.http import error_response_payload, status_code
from backend.presentation.rest.router import RunEventSource, create_api_router
from backend.presentation.sse.run_event_broker import RunEventBroker
from backend.shared.errors import AppError


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
    runtime_clock = clock if clock is not None else SystemClock()
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
        artifact_store=FileArtifactStore(app_config.codex.saved_artifacts_dir),
        transaction_manager=runtime_transaction_manager,
    )

    if runtime_run_dispatcher is not None:
        RecoverUnfinishedRunsUseCase(
            repository=chat_repository,
            run_dispatcher=runtime_run_dispatcher,
            transaction_manager=runtime_transaction_manager,
        ).execute(trace_id=_new_trace_id(runtime_id_generator))

    app = FastAPI(title="D-Concierge")
    _register_error_handlers(app)
    register_api_router(
        app,
        create_api_router(
            welcome_message=app_config.ui.welcome_message,
            input_suggestions=app_config.ui.input_suggestions,
            start_chat_usecase=start_chat_usecase,
            append_chat_run_usecase=append_chat_run_usecase,
            cancel_chat_run_usecase=cancel_chat_run_usecase,
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
        transaction_manager=transaction_manager,
    )
    reference_validator = CodexReferenceValidator(
        repository=chat_repository,
        codex_runner=runtime_codex_runner,
        validator_config=app_config.validator.codex,
        datasource_dir=app_config.datasource_dir,
        timeout_seconds=app_config.server.timeout_seconds,
        transaction_manager=transaction_manager,
    )
    answer_validator = ValidateAnswerUseCase(
        reference_validator=reference_validator,
        max_retries=app_config.validator.max_retries,
    )
    artifact_saver = SaveAdoptedArtifactsUseCase(
        artifact_store=FileArtifactStore(app_config.codex.saved_artifacts_dir),
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
            base_workdir=app_config.codex.workdir,
        ),
        trace_logger=trace_logger,
        timeout_seconds=app_config.server.timeout_seconds,
        transaction_manager=transaction_manager,
        clock=clock,
        id_generator=id_generator,
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


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: object, exc: AppError) -> JSONResponse:
        payload = error_response_payload(exc)
        return JSONResponse(
            status_code=status_code(exc.error_class),
            content=payload.model_dump(),
        )


def _new_trace_id(id_generator: IdGeneratorPort) -> str:
    return str(id_generator.new_uuid())

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from traceback import format_exception

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.router.registration import register_routes
from backend.application.account.recover_deleting_accounts import (
    RecoverDeletingAccountsCommand,
    RecoverDeletingAccountsUseCase,
)
from backend.application.chat.recover_deleting_chats import (
    RecoverDeletingChatsCommand,
    RecoverDeletingChatsUseCase,
)
from backend.application.execution.dto import RecoverUnfinishedRunsResult
from backend.application.execution.recover_unfinished_runs import (
    RecoverUnfinishedRunsCommand,
    RecoverUnfinishedRunsUseCase,
)
from backend.application.execution.run_event_broker import RunEventBroker
from backend.application.ports.database.dto import UnfinishedRun
from backend.application.ports.runtime.interface import (
    AccountDeletionDispatcherPort,
    ChatDeletionDispatcherPort,
)
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.infrastructure.config.loader import ConfigLoader
from backend.infrastructure.config.settings import AppSettings, StartupTraceLogSettings
from backend.infrastructure.database.repositories.account import (
    SqlAlchemyAccountRepository,
)
from backend.infrastructure.database.repositories.chat import SqlAlchemyChatRepository
from backend.infrastructure.database.session.factory import (
    create_database_engine,
    create_session_factory,
)
from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)
from backend.infrastructure.runtime.account_deletion_dispatcher import (
    DatabaseAccountDeletionExecutor,
    NullAccountDeletionDispatcher,
    ThreadedAccountDeletionDispatcher,
)
from backend.infrastructure.runtime.chat_deletion_dispatcher import (
    DatabaseChatDeletionExecutor,
    NullChatDeletionDispatcher,
    ThreadedChatDeletionDispatcher,
)
from backend.infrastructure.runtime.clock import SystemClock
from backend.infrastructure.runtime.codex_run_cancel_requester import (
    CodexRunCancelRequester,
    RunCancelRequesterLike,
)
from backend.infrastructure.runtime.run_execution_dispatcher import (
    AcceptedRunBackgroundExecutor,
    DatabaseChatRunExecutor,
    ThreadedRunExecutionDispatcher,
    create_codex_runner,
)
from backend.infrastructure.runtime.uuid_generator import UuidGenerator
from backend.infrastructure.trace_log.writer import TraceLogWriter
from backend.presentation.errors.http import (
    TraceErrorMiddleware,
    register_error_handlers,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId, new_trace_id


def create_app(config_path: Path, base_dir: Path | None = None) -> FastAPI:
    """FastAPIアプリケーションを組み立てる。"""

    config_loader = ConfigLoader()
    try:
        settings = config_loader.load(config_path, base_dir)
    except AppError as error:
        startup_trace_settings = config_loader.load_startup_trace_log_settings(
            config_path,
            base_dir,
        )
        _write_startup_configuration_failure(
            config_path,
            startup_trace_settings,
            error,
        )
        raise

    trace_log_writer = TraceLogWriter(
        root_dir=settings.trace_log.dir,
        timezone=settings.app.timezone,
        retention_days=settings.trace_log.retention_days,
        max_files_per_day=settings.trace_log.max_files_per_day,
    )
    trace_log_writer.prune_expired()
    id_generator = UuidGenerator()
    database_engine = create_database_engine(settings.database.url)
    session_factory = create_session_factory(database_engine)
    app = FastAPI(title="D-Concierge")
    app.state.settings = settings
    app.state.database_engine = database_engine
    app.state.session_factory = session_factory
    app.state.trace_log_writer = trace_log_writer
    app.state.run_event_broker = RunEventBroker()
    codex_runner = create_codex_runner(
        settings,
        _codex_script_path(base_dir, config_path),
    )
    app.state.codex_runner = codex_runner
    run_cancel_requester = CodexRunCancelRequester(codex_runner)
    app.state.run_execution_dispatcher = ThreadedRunExecutionDispatcher(
        executor=DatabaseChatRunExecutor(
            session_factory=session_factory,
            settings=settings,
            run_event_broker=app.state.run_event_broker,
            trace_log_writer=trace_log_writer,
            script_path=_codex_script_path(base_dir, config_path),
            codex_runner=codex_runner,
        )
    )
    app.state.chat_deletion_dispatcher = create_chat_deletion_dispatcher(
        session_factory,
        settings,
        trace_log_writer,
        run_cancel_requester,
    )
    app.state.account_deletion_dispatcher = _create_account_deletion_dispatcher_for_app(
        session_factory,
        settings,
        trace_log_writer,
        run_cancel_requester,
    )
    app.add_middleware(
        TraceErrorMiddleware,
        trace_log_writer=trace_log_writer,
        id_generator=id_generator,
    )
    register_error_handlers(app, trace_log_writer)
    register_routes(app)
    _recover_unfinished_runs(
        session_factory,
        SystemClock(settings.app.timezone),
        trace_log_writer,
    )
    _recover_deleting_chats(
        session_factory,
        app.state.chat_deletion_dispatcher,
        trace_log_writer,
    )
    _recover_deleting_accounts(
        session_factory,
        SystemClock(settings.app.timezone),
        app.state.account_deletion_dispatcher,
        trace_log_writer,
    )
    return app


def create_chat_deletion_dispatcher(
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    trace_log_writer: TraceLogWriter,
    cancel_requester: RunCancelRequesterLike,
) -> ThreadedChatDeletionDispatcher | NullChatDeletionDispatcher:
    """チャット物理削除dispatcherを生成する。"""

    return create_threaded_chat_deletion_dispatcher(
        session_factory,
        settings,
        trace_log_writer,
        cancel_requester,
    )


def create_threaded_chat_deletion_dispatcher(
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    trace_log_writer: TraceLogWriter,
    cancel_requester: RunCancelRequesterLike,
) -> ThreadedChatDeletionDispatcher:
    """チャット物理削除を実行するdispatcherを生成する。"""

    return ThreadedChatDeletionDispatcher(
        executor=DatabaseChatDeletionExecutor(
            session_factory=session_factory,
            settings=settings,
            trace_log_writer=trace_log_writer,
            cancel_requester=cancel_requester,
        )
    )


def create_account_deletion_dispatcher(
    session_factory: sessionmaker[Session] | None = None,
    settings: AppSettings | None = None,
    trace_log_writer: TraceLogWriter | None = None,
    cancel_requester: RunCancelRequesterLike | None = None,
) -> ThreadedAccountDeletionDispatcher | NullAccountDeletionDispatcher:
    """アカウント物理削除dispatcherを生成する。"""

    if (
        session_factory is None
        or settings is None
        or trace_log_writer is None
        or cancel_requester is None
    ):
        return NullAccountDeletionDispatcher()
    return create_threaded_account_deletion_dispatcher(
        session_factory,
        settings,
        trace_log_writer,
        cancel_requester,
    )


def create_threaded_account_deletion_dispatcher(
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    trace_log_writer: TraceLogWriter,
    cancel_requester: RunCancelRequesterLike,
) -> ThreadedAccountDeletionDispatcher:
    """アカウント物理削除を実行するdispatcherを生成する。"""

    return ThreadedAccountDeletionDispatcher(
        executor=DatabaseAccountDeletionExecutor(
            session_factory=session_factory,
            settings=settings,
            trace_log_writer=trace_log_writer,
            cancel_requester=cancel_requester,
        )
    )


def _create_account_deletion_dispatcher_for_app(
    session_factory: sessionmaker[Session],
    settings: AppSettings,
    trace_log_writer: TraceLogWriter,
    cancel_requester: RunCancelRequesterLike,
) -> ThreadedAccountDeletionDispatcher | NullAccountDeletionDispatcher:
    try:
        return create_account_deletion_dispatcher(
            session_factory,
            settings,
            trace_log_writer,
            cancel_requester,
        )
    except TypeError:
        return create_account_deletion_dispatcher()


def _codex_script_path(base_dir: Path | None, config_path: Path) -> Path:
    effective_base_dir = base_dir if base_dir is not None else config_path.parent
    return effective_base_dir / "infra/codex_docker/scripts/run_codex_docker.sh"


def _recover_unfinished_runs(
    session_factory: sessionmaker[Session],
    clock: SystemClock,
    trace_log_writer: TraceLogWriter,
) -> None:
    trace_id = new_trace_id()
    try:
        with session_factory() as session:
            repository = SqlAlchemyChatRepository(session)
            recovery_targets = repository.list_unfinished_runs_for_recovery()
            if not _should_recover_on_startup(recovery_targets):
                return
            use_case = RecoverUnfinishedRunsUseCase(
                repository=repository,
                transaction_manager=SqlAlchemyTransactionManager(session),
                background_executor=AcceptedRunBackgroundExecutor(),
                clock=clock,
            )
            result = use_case.execute(
                RecoverUnfinishedRunsCommand(trace_id=str(trace_id)),
            )
            _write_startup_recovery_completed(
                trace_log_writer,
                trace_id,
                len(recovery_targets),
                result,
            )
    except SQLAlchemyError as error:
        _write_startup_recovery_failed(trace_log_writer, trace_id, error)
        return


def _recover_deleting_accounts(
    session_factory: sessionmaker[Session],
    clock: SystemClock,
    dispatcher: AccountDeletionDispatcherPort,
    trace_log_writer: TraceLogWriter,
) -> None:
    trace_id = new_trace_id()
    try:
        with session_factory() as session:
            use_case = RecoverDeletingAccountsUseCase(
                repository=SqlAlchemyAccountRepository(session),
                transaction_manager=SqlAlchemyTransactionManager(session),
                dispatcher=dispatcher,
                trace_logger=trace_log_writer,
                clock=clock,
            )
            use_case.execute(RecoverDeletingAccountsCommand(trace_id=trace_id))
    except Exception as error:
        _write_startup_recovery_failed(trace_log_writer, trace_id, error)
        return


def _recover_deleting_chats(
    session_factory: sessionmaker[Session],
    dispatcher: ChatDeletionDispatcherPort,
    trace_log_writer: TraceLogWriter,
) -> None:
    trace_id = new_trace_id()
    try:
        with session_factory() as session:
            use_case = RecoverDeletingChatsUseCase(
                repository=SqlAlchemyChatRepository(session),
                dispatcher=dispatcher,
                trace_logger=trace_log_writer,
            )
            use_case.execute(RecoverDeletingChatsCommand(trace_id=trace_id))
    except SQLAlchemyError as error:
        _write_startup_recovery_failed(trace_log_writer, trace_id, error)
        return


def _should_recover_on_startup(
    recovery_targets: tuple[UnfinishedRun, ...],
) -> bool:
    return bool(recovery_targets)


def _write_startup_recovery_completed(
    trace_log_writer: TraceLogWriter,
    trace_id: TraceId,
    total_targets: int,
    result: RecoverUnfinishedRunsResult,
) -> None:
    message = (
        "起動時実行回復が完了しました。"
        f" total_targets={total_targets}"
        f" accepted_registered={result.accepted_registered}"
        f" error_terminalized={result.error_terminalized}"
        f" canceled_terminalized={result.canceled_terminalized}"
    )
    _write_startup_recovery_log(
        trace_log_writer,
        TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=trace_id,
            event_name="startup_recovery_completed",
            stage="app.recovery",
            error_type=ErrorType.SYSTEM,
            message=message,
            exception_type="",
            stacktrace="",
            http_method="",
            path="startup",
            status_code=0,
        ),
    )


def _write_startup_recovery_failed(
    trace_log_writer: TraceLogWriter,
    trace_id: TraceId,
    error: Exception,
) -> None:
    _write_startup_recovery_log(
        trace_log_writer,
        TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=trace_id,
            event_name="startup_recovery_failed",
            stage="app.recovery",
            error_type=ErrorType.SYSTEM,
            message=f"起動時実行回復対象の取得に失敗しました: {error}",
            exception_type=type(error).__name__,
            stacktrace="".join(
                format_exception(type(error), error, error.__traceback__),
            ),
            http_method="",
            path="startup",
            status_code=500,
        ),
    )


def _write_startup_recovery_log(
    trace_log_writer: TraceLogWriter,
    record: TraceLogRecord,
) -> None:
    try:
        trace_log_writer.write(record)
    except Exception:
        return


def _write_startup_configuration_failure(
    config_path: Path,
    trace_log_settings: StartupTraceLogSettings,
    error: AppError,
) -> None:
    trace_log_writer = TraceLogWriter(
        root_dir=trace_log_settings.dir,
        timezone=trace_log_settings.timezone,
        retention_days=trace_log_settings.retention_days,
        max_files_per_day=trace_log_settings.max_files_per_day,
    )
    try:
        trace_log_writer.prune_expired()
        trace_id = new_trace_id()
        trace_log_writer.write(
            TraceLogRecord(
                occurred_at=datetime.now(UTC),
                trace_id=trace_id,
                event_name="app_startup_failed",
                stage="app.factory",
                error_type=ErrorType.CONFIGURATION,
                message=error.diagnostic_message,
                exception_type=type(error).__name__,
                stacktrace="".join(
                    format_exception(type(error), error, error.__traceback__),
                ),
                http_method="",
                path=str(config_path),
                status_code=500,
            )
        )
    except Exception:
        return

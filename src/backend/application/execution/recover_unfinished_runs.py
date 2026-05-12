from dataclasses import dataclass

from backend.application.ports.database.dto import UnfinishedRun
from backend.application.ports.database.interface import (
    RecoveryRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.interface import RunExecutionDispatcherPort
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.ports.trace_log.interface import TraceLoggerPort
from backend.application.transactions import NoopTransactionManager
from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.exception import exception_stacktrace
from backend.shared.user_messages import CANCELED_MESSAGE, RECOVERY_ERROR_MESSAGE


@dataclass(frozen=True, slots=True)
class RecoverySummary:
    """起動時回復の処理件数。"""

    reregistered: int
    marked_error: int
    canceled: int
    failed: int


@dataclass(slots=True)
class _RecoveryCounter:
    reregistered: int = 0
    marked_error: int = 0
    canceled: int = 0
    failed: int = 0

    def to_summary(self) -> RecoverySummary:
        """公開用の回復処理サマリへ変換する。"""
        return RecoverySummary(
            reregistered=self.reregistered,
            marked_error=self.marked_error,
            canceled=self.canceled,
            failed=self.failed,
        )


class RecoverUnfinishedRunsUseCase:
    """アプリ起動時に未完了runを再登録または終端状態へ整合する。"""

    def __init__(
        self,
        repository: RecoveryRepositoryPort,
        run_dispatcher: RunExecutionDispatcherPort,
        transaction_manager: TransactionManagerPort | None = None,
        trace_logger: TraceLoggerPort | None = None,
    ) -> None:
        self._repository = repository
        self._run_dispatcher = run_dispatcher
        self._trace_logger = trace_logger
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, trace_id: str) -> RecoverySummary:
        """起動時回復対象の未完了runを状態別に処理する。"""
        counter = _RecoveryCounter()
        with self._transaction_manager.transaction():
            runs = self._repository.list_unfinished_runs_for_recovery()
        for run in runs:
            self._recover_one(run, counter, trace_id)
        return counter.to_summary()

    def _recover_one(
        self,
        run: UnfinishedRun,
        counter: _RecoveryCounter,
        trace_id: str,
    ) -> None:
        try:
            match run.state:
                case RunState.ACCEPTED:
                    self._recover_accepted(run, counter, trace_id)
                case RunState.RUNNING | RunState.VALIDATING:
                    self._mark_error(run)
                    counter.marked_error += 1
                case RunState.CANCEL_REQUESTED:
                    with self._transaction_manager.transaction():
                        self._repository.set_run_state(
                            run.chat_id,
                            run.run_id,
                            RunState.CANCELED,
                            CANCELED_MESSAGE,
                        )
                    counter.canceled += 1
                case _:
                    return
        except AppError as exc:
            counter.failed += 1
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="recovery_failed",
                    stage="startup_recovery",
                    chat_id=run.chat_id,
                    run_id=run.run_id,
                    error_type=exc.error_type.value,
                    exception_type=type(exc).__name__,
                    run_state=RunState.ERROR.value,
                    stacktrace=exception_stacktrace(exc),
                    message=(
                        exc.diagnostic_message
                        if exc.trace
                        else "起動時回復処理でエラーが発生しました。"
                    ),
                )
            )

    def _recover_accepted(
        self,
        run: UnfinishedRun,
        counter: _RecoveryCounter,
        trace_id: str,
    ) -> None:
        result = self._run_dispatcher.register(run.chat_id, run.run_id, trace_id)
        if result.status in {
            DispatchStatus.REGISTERED,
            DispatchStatus.ALREADY_REGISTERED,
        }:
            counter.reregistered += 1
            return

        self._mark_error(run)
        counter.marked_error += 1
        counter.failed += 1
        self._write_trace(
            TraceLogRecord(
                trace_id=trace_id,
                event_name="recovery_failed",
                stage="startup_recovery",
                chat_id=run.chat_id,
                run_id=run.run_id,
                error_type=ErrorType.SYSTEM.value,
                run_state=RunState.ERROR.value,
                process_result=result.failure_reason,
                message="受付済みrunの起動時再登録に失敗しました。",
            )
        )

    def _mark_error(self, run: UnfinishedRun) -> None:
        with self._transaction_manager.transaction():
            self._repository.set_run_state(
                run.chat_id,
                run.run_id,
                RunState.ERROR,
                RECOVERY_ERROR_MESSAGE,
            )

    def _write_trace(self, record: TraceLogRecord) -> None:
        if self._trace_logger is not None:
            self._trace_logger.write(record)

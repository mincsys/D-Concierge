from __future__ import annotations

from dataclasses import dataclass

from backend.application.execution.cancel_chat_run import RUN_CANCELED_MESSAGE
from backend.application.execution.dto import RecoverUnfinishedRunsResult
from backend.application.execution.interfaces import (
    BackgroundExecutorLike,
    RecoverUnfinishedRunsRepositoryLike,
)
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import ClockPort
from backend.domain.execution.run_state import RunState
from backend.shared.user_messages import SYSTEM_ERROR


@dataclass(frozen=True, slots=True)
class RecoverUnfinishedRunsCommand:
    """起動時実行回復要求。"""

    trace_id: str


class RecoverUnfinishedRunsUseCase:
    """起動時に未完了runの状態を整合する。"""

    def __init__(
        self,
        *,
        repository: RecoverUnfinishedRunsRepositoryLike,
        transaction_manager: TransactionManagerPort,
        background_executor: BackgroundExecutorLike,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._background_executor = background_executor
        self._clock = clock

    def execute(
        self,
        command: RecoverUnfinishedRunsCommand,
    ) -> RecoverUnfinishedRunsResult:
        """未完了runを状態別に再登録または終端化する。"""

        accepted_registered = 0
        error_terminalized = 0
        canceled_terminalized = 0

        for run in self._repository.list_unfinished_runs_for_recovery():
            if run.state == RunState.ACCEPTED.value:
                if self._background_executor.submit(run.run_id):
                    accepted_registered += 1
                    continue
                with self._transaction_manager:
                    if self._repository.update_run_state_if_current(
                        run.run_id,
                        RunState.ACCEPTED.value,
                        RunState.ERROR.value,
                        SYSTEM_ERROR,
                    ):
                        error_terminalized += 1
                continue

            if run.state in _LOST_EXECUTION_STATES:
                with self._transaction_manager:
                    if self._repository.update_run_state_if_current(
                        run.run_id,
                        run.state,
                        RunState.ERROR.value,
                        SYSTEM_ERROR,
                    ):
                        error_terminalized += 1
                continue

            if run.state == RunState.CANCEL_REQUESTED.value:
                with self._transaction_manager:
                    if self._repository.update_run_state_if_current(
                        run.run_id,
                        RunState.CANCEL_REQUESTED.value,
                        RunState.CANCELED.value,
                        RUN_CANCELED_MESSAGE,
                    ):
                        canceled_terminalized += 1

        return RecoverUnfinishedRunsResult(
            accepted_registered=accepted_registered,
            error_terminalized=error_terminalized,
            canceled_terminalized=canceled_terminalized,
        )


_LOST_EXECUTION_STATES = frozenset(
    {
        RunState.RUNNING.value,
        RunState.VALIDATING.value,
    }
)

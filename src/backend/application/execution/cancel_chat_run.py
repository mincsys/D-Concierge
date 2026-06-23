from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.application.execution.dto import CancelChatRunResult
from backend.application.execution.interfaces import (
    CancelChatRunRepositoryLike,
    CodexRunCancellationLike,
    RunEventPublisherLike,
)
from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.runtime.interface import ClockPort
from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId

RUN_CANCELING_MESSAGE = "処理をキャンセルしています。"
RUN_CANCELED_MESSAGE = "処理をキャンセルしました。"


@dataclass(frozen=True, slots=True)
class CancelChatRunCommand:
    """チャットrunキャンセル要求。"""

    authenticated_user_id: str
    chat_id: UUID
    run_id: UUID
    trace_id: TraceId


class CancelChatRunUseCase:
    """チャットrunキャンセル受付を調停する。"""

    def __init__(
        self,
        *,
        repository: CancelChatRunRepositoryLike,
        transaction_manager: TransactionManagerPort,
        codex_runner: CodexRunCancellationLike,
        event_publisher: RunEventPublisherLike,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._codex_runner = codex_runner
        self._event_publisher = event_publisher
        self._clock = clock

    def execute(self, command: CancelChatRunCommand) -> CancelChatRunResult:
        """対象runを状態別にキャンセル受付へ進める。"""

        target = self._repository.get_cancel_target(
            command.authenticated_user_id,
            command.chat_id,
            command.run_id,
        )
        if target is None:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="対象runが見つかりません。",
            )
        if target.chat_state == ChatState.DELETING.value:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        if target.state not in _CANCELABLE_STATES:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="キャンセルできないrun状態です。",
            )

        with self._transaction_manager:
            updated = self._repository.update_run_state_if_current(
                command.run_id,
                target.state,
                RunState.CANCEL_REQUESTED.value,
                RUN_CANCELING_MESSAGE,
            )
        if not updated:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="run状態が更新されています。",
            )
        self._event_publisher.publish(
            command.run_id,
            "state",
            RunState.CANCEL_REQUESTED.value,
            None,
        )

        if target.state == RunState.ACCEPTED.value:
            with self._transaction_manager:
                self._repository.update_run_state_if_current(
                    command.run_id,
                    RunState.CANCEL_REQUESTED.value,
                    RunState.CANCELED.value,
                    RUN_CANCELED_MESSAGE,
                )
            self._event_publisher.publish(
                command.run_id,
                "canceled",
                RunState.CANCELED.value,
                RUN_CANCELED_MESSAGE,
            )
            return CancelChatRunResult(
                state=RunState.CANCELED.value,
                user_message=RUN_CANCELED_MESSAGE,
            )

        cancel_result = self._codex_runner.cancel(
            command.chat_id,
            command.run_id,
            str(command.trace_id),
        )
        if cancel_result.status in _RUNNER_ALREADY_STOPPED_STATUSES:
            return self._finish_as_canceled(command.run_id)
        return CancelChatRunResult(
            state=RunState.CANCEL_REQUESTED.value,
            user_message=RUN_CANCELING_MESSAGE,
        )

    def _finish_as_canceled(self, run_id: UUID) -> CancelChatRunResult:
        with self._transaction_manager:
            updated = self._repository.update_run_state_if_current(
                run_id,
                RunState.CANCEL_REQUESTED.value,
                RunState.CANCELED.value,
                RUN_CANCELED_MESSAGE,
            )
        if not updated:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="run状態が更新されています。",
            )
        self._event_publisher.publish(
            run_id,
            "canceled",
            RunState.CANCELED.value,
            RUN_CANCELED_MESSAGE,
        )
        return CancelChatRunResult(
            state=RunState.CANCELED.value,
            user_message=RUN_CANCELED_MESSAGE,
        )


_CANCELABLE_STATES = frozenset(
    {
        RunState.ACCEPTED.value,
        RunState.RUNNING.value,
        RunState.VALIDATING.value,
    }
)
_RUNNER_ALREADY_STOPPED_STATUSES = frozenset({"already_exited", "not_registered"})

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.application.execution.execute_chat_run import RunEvent
from backend.application.execution.run_event_type import RunEventType
from backend.application.ports.codex.cancel_request_result import CancelRequestResult
from backend.application.ports.codex.interface import CancelRequesterPort
from backend.application.ports.database.interface import (
    CancelChatRunRepositoryPort,
    TransactionManagerPort,
)
from backend.application.transactions import NoopTransactionManager
from backend.domain.execution.run_state import RunState
from backend.domain.execution.run_state_policy import RunStatePolicy
from backend.shared.error_class import ErrorClass
from backend.shared.errors import AppError
from backend.shared.user_messages import (
    CANCEL_NOT_ALLOWED_MESSAGE,
    CANCEL_REQUESTED_MESSAGE,
    CANCELED_MESSAGE,
)


@dataclass(frozen=True, slots=True)
class CancelChatRunResult:
    """キャンセル受付結果。"""

    run_id: UUID
    state: RunState
    user_message: str


class CancelEventPublisher(Protocol):
    """キャンセル状態変更イベントの発行境界。"""

    def publish(self, event: RunEvent) -> None:
        """キャンセル関連イベントを発行する。"""


class CancelChatRunUseCase:
    """チャット実行処理のキャンセル要求を調停する。"""

    def __init__(
        self,
        repository: CancelChatRunRepositoryPort,
        cancel_requester: CancelRequesterPort | None = None,
        event_publisher: CancelEventPublisher | None = None,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._cancel_requester = cancel_requester
        self._event_publisher = event_publisher
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def request_cancel(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> CancelChatRunResult:
        """キャンセル可能runをキャンセル要求として受け付ける。"""
        _ = trace_id
        with self._transaction_manager.transaction():
            current_state = self._repository.get_run_state(chat_id, run_id)
            if not RunStatePolicy.is_cancelable(current_state):
                raise AppError(ErrorClass.CONFLICT, CANCEL_NOT_ALLOWED_MESSAGE)

            updated = self._repository.update_run_state_if_current(
                chat_id=chat_id,
                run_id=run_id,
                expected_states=(current_state,),
                state=RunState.CANCEL_REQUESTED,
                user_message=CANCEL_REQUESTED_MESSAGE,
            )
        if not updated:
            raise AppError(ErrorClass.CONFLICT, CANCEL_NOT_ALLOWED_MESSAGE)
        self._publish(
            RunEvent(
                event=RunEventType.STATE,
                chat_id=chat_id,
                run_id=run_id,
                state=RunState.CANCEL_REQUESTED,
            )
        )
        if current_state is RunState.ACCEPTED:
            self._complete_cancel(chat_id, run_id)
        elif current_state in {RunState.RUNNING, RunState.VALIDATING}:
            cancel_result: CancelRequestResult = (
                self._cancel_requester.request_cancel(run_id)
                if self._cancel_requester is not None
                else CancelRequestResult.NOT_REGISTERED
            )
            if cancel_result in {
                CancelRequestResult.ALREADY_EXITED,
                CancelRequestResult.NOT_REGISTERED,
            }:
                self._complete_cancel(chat_id, run_id)

        return CancelChatRunResult(
            run_id=run_id,
            state=RunState.CANCEL_REQUESTED,
            user_message=CANCEL_REQUESTED_MESSAGE,
        )

    def _complete_cancel(self, chat_id: UUID, run_id: UUID) -> None:
        with self._transaction_manager.transaction():
            updated = self._repository.update_run_state_if_current(
                chat_id=chat_id,
                run_id=run_id,
                expected_states=(RunState.CANCEL_REQUESTED,),
                state=RunState.CANCELED,
                user_message=CANCELED_MESSAGE,
            )
        if not updated:
            return
        self._publish(
            RunEvent(
                event=RunEventType.CANCELED,
                chat_id=chat_id,
                run_id=run_id,
                state=RunState.CANCELED,
                user_message=CANCELED_MESSAGE,
            )
        )

    def _publish(self, event: RunEvent) -> None:
        if self._event_publisher is not None:
            self._event_publisher.publish(event)

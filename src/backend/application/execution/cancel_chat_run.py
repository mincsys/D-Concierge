from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from backend.application.execution.execute_chat_run import RunEvent
from backend.domain.execution.run_state_policy import RunState, RunStatePolicy
from backend.shared.errors import AppError, ErrorClass

CancelRequestResult = Literal["sent", "already_exited", "not_registered"]
CANCELED_MESSAGE = "処理をキャンセルしました。"
CANCEL_REQUESTED_MESSAGE = "処理をキャンセルしています。"


@dataclass(frozen=True, slots=True)
class CancelChatRunResult:
    """キャンセル受付結果。"""

    run_id: UUID
    state: Literal["キャンセル要求中"]
    user_message: str


class CancelChatRunRepository(Protocol):
    """キャンセル受付に必要なRepository境界。"""

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """対象runの現在状態を返す。"""

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        """対象runをキャンセルする。"""

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
    ) -> bool:
        """期待状態に一致する場合だけrun状態を更新する。"""


class CancelRequester(Protocol):
    """実行中Codexプロセスへの終了要求境界。"""

    def request_cancel(self, run_id: UUID) -> CancelRequestResult:
        """対象runの実行プロセスへ終了要求を送る。"""


class CancelEventPublisher(Protocol):
    """キャンセル状態変更イベントの発行境界。"""

    def publish(self, event: RunEvent) -> None:
        """キャンセル関連イベントを発行する。"""


class CancelChatRunUseCase:
    """チャット実行処理のキャンセル要求を調停する。"""

    def __init__(
        self,
        repository: CancelChatRunRepository,
        cancel_requester: CancelRequester | None = None,
        event_publisher: CancelEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._cancel_requester = cancel_requester
        self._event_publisher = event_publisher

    def request_cancel(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> CancelChatRunResult:
        """キャンセル可能runをキャンセル要求として受け付ける。"""
        _ = trace_id
        current_state = self._repository.get_run_state(chat_id, run_id)
        if not RunStatePolicy.is_cancelable(current_state):
            raise AppError(ErrorClass.CONFLICT, "この処理はキャンセルできません。")

        updated = self._repository.update_run_state_if_current(
            chat_id=chat_id,
            run_id=run_id,
            expected_states=(current_state,),
            state="キャンセル要求中",
            user_message=CANCEL_REQUESTED_MESSAGE,
        )
        if not updated:
            raise AppError(ErrorClass.CONFLICT, "この処理はキャンセルできません。")
        self._publish(
            RunEvent(
                event="state",
                chat_id=chat_id,
                run_id=run_id,
                state="キャンセル要求中",
            )
        )
        if current_state == "受付":
            self._complete_cancel(chat_id, run_id)
        elif current_state in {"実行中", "検証中"}:
            cancel_result: CancelRequestResult = (
                self._cancel_requester.request_cancel(run_id)
                if self._cancel_requester is not None
                else "not_registered"
            )
            if cancel_result in {"already_exited", "not_registered"}:
                self._complete_cancel(chat_id, run_id)

        return CancelChatRunResult(
            run_id=run_id,
            state="キャンセル要求中",
            user_message=CANCEL_REQUESTED_MESSAGE,
        )

    def _complete_cancel(self, chat_id: UUID, run_id: UUID) -> None:
        updated = self._repository.update_run_state_if_current(
            chat_id=chat_id,
            run_id=run_id,
            expected_states=("キャンセル要求中",),
            state="キャンセル済み",
            user_message=CANCELED_MESSAGE,
        )
        if not updated:
            return
        self._publish(
            RunEvent(
                event="canceled",
                chat_id=chat_id,
                run_id=run_id,
                state="キャンセル済み",
                user_message=CANCELED_MESSAGE,
            )
        )

    def _publish(self, event: RunEvent) -> None:
        if self._event_publisher is not None:
            self._event_publisher.publish(event)

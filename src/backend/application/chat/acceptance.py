from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.application.execution.dispatcher import DispatchResult
from backend.domain.execution.run_state_policy import RunState
from backend.infrastructure.memory.repository import AcceptedRun
from backend.shared.errors import AppError, ErrorClass

DISPATCH_FAILURE_MESSAGE = "チャット実行処理を開始できませんでした。"


@dataclass(frozen=True, slots=True)
class AcceptedChatRunResult:
    """チャット実行受付結果。"""

    chat_id: UUID
    run_id: UUID
    sse_url: str
    state: RunState


class RunExecutionDispatcher(Protocol):
    """受付済みrunをバックグラウンド登録する境界。"""

    def register(self, chat_id: UUID, run_id: UUID) -> DispatchResult:
        """対象runの実行を登録する。"""


class AcceptedRunStateRepository(Protocol):
    """受付済みrunの状態更新境界。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """runの状態と利用者向けメッセージを更新する。"""


def accepted_chat_run_result(accepted: AcceptedRun) -> AcceptedChatRunResult:
    """Repository受付結果を画面向け受付結果へ変換する。"""
    return AcceptedChatRunResult(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        sse_url=f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse",
        state=accepted.state,
    )


def register_accepted_run(
    repository: AcceptedRunStateRepository,
    run_dispatcher: RunExecutionDispatcher | None,
    accepted: AcceptedRun,
) -> None:
    """受付済みrunを登録し、登録失敗時はrunをエラーへ整合する。"""
    if run_dispatcher is None:
        return

    result = run_dispatcher.register(accepted.chat_id, accepted.run_id)
    if result.status == "failed":
        repository.set_run_state(
            accepted.chat_id,
            accepted.run_id,
            "エラー",
            DISPATCH_FAILURE_MESSAGE,
        )
        raise AppError(ErrorClass.SYSTEM, DISPATCH_FAILURE_MESSAGE)

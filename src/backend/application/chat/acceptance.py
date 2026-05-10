from dataclasses import dataclass
from uuid import UUID

from backend.application.ports.database.dto import AcceptedRun
from backend.application.ports.database.interface import (
    AcceptedRunStateRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import RunExecutionDispatcherPort
from backend.domain.execution.run_state_policy import RunState
from backend.shared.errors import AppError, ErrorClass

DISPATCH_FAILURE_MESSAGE = "チャット実行処理を開始できませんでした。"


@dataclass(frozen=True, slots=True)
class AcceptedChatRunResult:
    """チャット実行受付結果。"""

    chat_id: UUID
    run_id: UUID
    sse_url: str
    state: RunState


def accepted_chat_run_result(accepted: AcceptedRun) -> AcceptedChatRunResult:
    """Repository受付結果を画面向け受付結果へ変換する。"""
    return AcceptedChatRunResult(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        sse_url=f"/api/chats/{accepted.chat_id}/runs/{accepted.run_id}/sse",
        state=accepted.state,
    )


def register_accepted_run(
    repository: AcceptedRunStateRepositoryPort,
    transaction_manager: TransactionManagerPort,
    run_dispatcher: RunExecutionDispatcherPort | None,
    accepted: AcceptedRun,
    trace_id: str,
) -> None:
    """受付済みrunを登録し、登録失敗時はrunをエラーへ整合する。"""
    if run_dispatcher is None:
        return

    result = run_dispatcher.register(accepted.chat_id, accepted.run_id, trace_id)
    if result.status == "failed":
        with transaction_manager.transaction():
            repository.set_run_state(
                accepted.chat_id,
                accepted.run_id,
                "エラー",
                DISPATCH_FAILURE_MESSAGE,
            )
        raise AppError(ErrorClass.SYSTEM, DISPATCH_FAILURE_MESSAGE)

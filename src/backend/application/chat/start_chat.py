from typing import Protocol
from uuid import UUID

from backend.application.chat.acceptance import (
    AcceptedChatRunResult,
    RunExecutionDispatcher,
    accepted_chat_run_result,
    register_accepted_run,
)
from backend.domain.execution.run_state_policy import RunState
from backend.infrastructure.memory.repository import AcceptedRun


class StartChatRepository(Protocol):
    """新規チャット受付に必要なRepository境界。"""

    def create_chat_with_first_run(self, user_instruction: str) -> AcceptedRun:
        """新規チャット、初回run、初回指示を保存する。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """runの状態と利用者向けメッセージを更新する。"""


class StartChatUseCase:
    """新規チャットと初回run受付を調停する。"""

    def __init__(
        self,
        repository: StartChatRepository,
        run_dispatcher: RunExecutionDispatcher | None,
    ) -> None:
        self._repository = repository
        self._run_dispatcher = run_dispatcher

    def execute(self, user_instruction: str, trace_id: str) -> AcceptedChatRunResult:
        """初回指示を受付状態で保存し、実行dispatcherへ登録する。"""
        _ = trace_id
        accepted = self._repository.create_chat_with_first_run(user_instruction)
        register_accepted_run(self._repository, self._run_dispatcher, accepted)
        return accepted_chat_run_result(accepted)

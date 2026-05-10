from uuid import UUID

from backend.application.chat.acceptance import (
    AcceptedChatRunResult,
    accepted_chat_run_result,
    register_accepted_run,
)
from backend.application.ports.database.interface import AppendChatRunRepositoryPort
from backend.application.ports.runtime.interface import RunExecutionDispatcherPort


class AppendChatRunUseCase:
    """既存チャットへの継続run受付を調停する。"""

    def __init__(
        self,
        repository: AppendChatRunRepositoryPort,
        run_dispatcher: RunExecutionDispatcherPort | None,
    ) -> None:
        self._repository = repository
        self._run_dispatcher = run_dispatcher

    def execute(
        self,
        chat_id: UUID,
        user_instruction: str,
        trace_id: str,
    ) -> AcceptedChatRunResult:
        """継続指示を受付状態で保存し、実行dispatcherへ登録する。"""
        _ = trace_id
        accepted = self._repository.append_run(chat_id, user_instruction)
        register_accepted_run(self._repository, self._run_dispatcher, accepted)
        return accepted_chat_run_result(accepted)

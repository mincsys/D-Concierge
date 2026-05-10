from backend.application.chat.acceptance import (
    AcceptedChatRunResult,
    accepted_chat_run_result,
    register_accepted_run,
)
from backend.application.ports.database.interface import StartChatRepositoryPort
from backend.application.ports.runtime.interface import RunExecutionDispatcherPort


class StartChatUseCase:
    """新規チャットと初回run受付を調停する。"""

    def __init__(
        self,
        repository: StartChatRepositoryPort,
        run_dispatcher: RunExecutionDispatcherPort | None,
    ) -> None:
        self._repository = repository
        self._run_dispatcher = run_dispatcher

    def execute(self, user_instruction: str, trace_id: str) -> AcceptedChatRunResult:
        """初回指示を受付状態で保存し、実行dispatcherへ登録する。"""
        _ = trace_id
        accepted = self._repository.create_chat_with_first_run(user_instruction)
        register_accepted_run(self._repository, self._run_dispatcher, accepted)
        return accepted_chat_run_result(accepted)

from uuid import UUID

from backend.application.chat.acceptance import (
    AcceptedChatRunResult,
    accepted_chat_run_result,
    register_accepted_run,
)
from backend.application.ports.database.interface import (
    AppendChatRunRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import RunExecutionDispatcherPort
from backend.application.transactions import NoopTransactionManager


class AppendChatRunUseCase:
    """既存チャットへの継続run受付を調停する。"""

    def __init__(
        self,
        repository: AppendChatRunRepositoryPort,
        run_dispatcher: RunExecutionDispatcherPort | None,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._run_dispatcher = run_dispatcher
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(
        self,
        chat_id: UUID,
        user_instruction: str,
        trace_id: str,
        user_id: str = "",
    ) -> AcceptedChatRunResult:
        """継続指示を受付状態で保存し、実行dispatcherへ登録する。"""
        with self._transaction_manager.transaction():
            accepted = self._repository.append_run(
                chat_id,
                user_instruction,
                user_id=user_id,
            )
        register_accepted_run(
            self._repository,
            self._transaction_manager,
            self._run_dispatcher,
            accepted,
            trace_id,
        )
        return accepted_chat_run_result(accepted)

from __future__ import annotations

from dataclasses import dataclass

from backend.application.chat._shared import (
    build_sse_url,
    build_title,
    dispatcher_failure,
    normalize_instruction,
)
from backend.application.chat.dto import ChatAcceptedResult
from backend.application.chat.interfaces import (
    RunExecutionDispatcherLike,
    StartChatRepositoryLike,
)
from backend.application.ports.database.interface import (
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import (
    ClockPort,
    IdGeneratorPort,
)
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class StartChatCommand:
    """新規チャット開始要求。"""

    authenticated_user_id: str
    user_instruction: str
    trace_id: TraceId


class StartChatUseCase:
    """新規チャット開始を調停する。"""

    def __init__(
        self,
        *,
        repository: StartChatRepositoryLike,
        transaction_manager: TransactionManagerPort,
        dispatcher: RunExecutionDispatcherLike,
        id_generator: IdGeneratorPort,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._dispatcher = dispatcher
        self._id_generator = id_generator
        self._clock = clock

    def execute(self, command: StartChatCommand) -> ChatAcceptedResult:
        """初回指示を保存し、実行登録後に受付結果を返す。"""

        user_instruction = normalize_instruction(command.user_instruction)
        chat_id = self._id_generator.new_uuid()
        run_id = self._id_generator.new_uuid()
        session_id = self._id_generator.new_uuid()
        started_at = self._clock.now_utc()

        with self._transaction_manager:
            accepted_run = self._repository.create_chat_with_first_run(
                command.authenticated_user_id,
                chat_id,
                run_id,
                session_id,
                build_title(user_instruction),
                user_instruction,
                str(command.trace_id),
                started_at,
            )

        dispatch_result = self._dispatcher.register(
            accepted_run.chat_id,
            accepted_run.run_id,
            str(command.trace_id),
        )
        if dispatch_result.status == "failed":
            with self._transaction_manager:
                self._repository.mark_run_error(
                    accepted_run.run_id,
                    dispatch_result.diagnostic_message,
                )
            raise dispatcher_failure(dispatch_result.diagnostic_message)

        return ChatAcceptedResult(
            chat_id=accepted_run.chat_id,
            run_id=accepted_run.run_id,
            sse_url=build_sse_url(accepted_run.chat_id, accepted_run.run_id),
            state=accepted_run.state,
        )

from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.ports.codex.dto import CodexRunResult
from backend.application.ports.database.interface import (
    ChatRuntimeRepositoryPort,
    TransactionManagerPort,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.codex_workspace_preparer import (
    prepare_generation_workspace,
)
from backend.infrastructure.codex.intermediate_messages import (
    CodexIntermediateMessageStreamer,
)
from backend.infrastructure.config.models import CodexDockerConfig, GeneratorConfig


class InfrastructureCodexRunner(Protocol):
    """実CodexRunnerの生成実行境界。"""

    def run_generation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """生成用Codex Docker実行を行う。"""


class CodexGenerationRunnerAdapter:
    """application層の生成実行IFへCodexRunnerを適合させる。"""

    def __init__(
        self,
        repository: ChatRuntimeRepositoryPort,
        codex_runner: InfrastructureCodexRunner,
        generator_config: GeneratorConfig,
        codex_docker_config: CodexDockerConfig,
        datasource_dir: Path,
        timeout_seconds: int,
        transaction_manager: TransactionManagerPort,
    ) -> None:
        self._repository = repository
        self._codex_runner = codex_runner
        self._generator_config = generator_config
        self._codex_docker_config = codex_docker_config
        self._datasource_dir = datasource_dir
        self._timeout_seconds = timeout_seconds
        self._transaction_manager = transaction_manager

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int | None = None,
        trace_id: str = "",
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """生成用CodexRunnerを実行し、実行UseCase向けの結果へ変換する。"""
        with self._transaction_manager.transaction():
            context = self._repository.get_chat_runtime_context(chat_id)
        workdir = (
            self._generator_config.workdir / context.user_id / str(context.session_id)
        )
        prepare_generation_workspace(workdir)
        intermediate_streamer = CodexIntermediateMessageStreamer(
            on_intermediate_message
        )
        result = self._codex_runner.run_generation(
            CodexRunRequest(
                run_id=run_id,
                prompt=user_instruction,
                codex_home=self._generator_config.home,
                workdir=workdir,
                datasource_dir=self._datasource_dir,
                output_schema=self._generator_config.output_schema,
                docker_config=self._codex_docker_config,
                artifact_mount_dir=None,
                codex_conversation_id=context.generation_conversation_id,
                timeout_seconds=(
                    timeout_seconds
                    if timeout_seconds is not None
                    else self._timeout_seconds
                ),
                trace_id=trace_id,
                on_event=intermediate_streamer.accept
                if on_intermediate_message is not None
                else None,
            )
        )
        with self._transaction_manager.transaction():
            self._repository.save_generation_conversation_id(
                chat_id,
                result.codex_conversation_id,
            )
        return CodexRunResult(
            conversation_id=result.codex_conversation_id,
            intermediate_messages=(
                ()
                if on_intermediate_message is not None
                else _intermediate_messages(result)
            ),
            final_answer_json=result.final_message,
        )


def _intermediate_messages(
    result: InfrastructureCodexRunResult,
) -> tuple[str, ...]:
    agent_messages: list[str] = []
    intermediate_streamer = CodexIntermediateMessageStreamer(agent_messages.append)
    for event in result.events:
        intermediate_streamer.accept(event)
    return tuple(agent_messages)

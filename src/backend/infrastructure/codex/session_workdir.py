from pathlib import Path
from uuid import UUID

from backend.application.ports.database.interface import ChatRuntimeRepositoryPort


class CodexSessionWorkdirResolver:
    """チャットの内部IDから生成用Codex作業領域を解決する。"""

    def __init__(
        self, repository: ChatRuntimeRepositoryPort, base_workdir: Path
    ) -> None:
        self._repository = repository
        self._base_workdir = base_workdir

    def resolve_generation_workdir(self, chat_id: UUID) -> Path:
        """生成用Codexのセッション作業領域を返す。"""
        context = self._repository.get_chat_runtime_context(chat_id)
        return self._base_workdir / context.user_id / str(context.session_id)

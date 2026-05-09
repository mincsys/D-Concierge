from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.infrastructure.memory.repository import ChatRuntimeContext


class ChatRuntimeRepository(Protocol):
    """Codex作業領域解決に必要なチャット実行コンテキスト境界。"""

    def get_chat_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext:
        """チャット単位のCodex実行コンテキストを返す。"""


class CodexSessionWorkdirResolver:
    """チャットの内部IDから生成用Codex作業領域を解決する。"""

    def __init__(self, repository: ChatRuntimeRepository, base_workdir: Path) -> None:
        self._repository = repository
        self._base_workdir = base_workdir

    def resolve_generation_workdir(self, chat_id: UUID) -> Path:
        """生成用Codexのセッション作業領域を返す。"""
        context = self._repository.get_chat_runtime_context(chat_id)
        return self._base_workdir / str(context.local_user_id) / str(context.session_id)

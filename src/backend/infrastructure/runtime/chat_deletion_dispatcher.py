from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from backend.application.chat.delete_chat import (
    ExecuteChatDeletionCommand,
    ExecuteChatDeletionUseCase,
)
from backend.application.ports.runtime.interface import (
    ChatDeletionDispatchResult,
    ChatDeletionDispatchStatus,
)
from backend.infrastructure.codex.session_workdir_cleanup import (
    CodexSessionWorkdirCleanup,
)
from backend.infrastructure.config.settings import AppSettings
from backend.infrastructure.database.repositories.chat import SqlAlchemyChatRepository
from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
from backend.infrastructure.runtime.codex_run_cancel_requester import (
    RunCancelRequesterLike,
)
from backend.infrastructure.trace_log.writer import TraceLogWriter
from backend.shared.tracing.trace_id import TraceId


class ChatDeletionExecutorLike(Protocol):
    """dispatcherから呼び出すチャット物理削除本体。"""

    def execute(self, chat_id: UUID, trace_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class NullChatDeletionDispatcher:
    """物理削除を起動せず削除ジョブ登録済みとして扱うdispatcher。"""

    def dispatch_chat_deletion(
        self,
        chat_id: UUID,
        trace_id: str,
    ) -> ChatDeletionDispatchResult:
        return ChatDeletionDispatchResult(
            status=ChatDeletionDispatchStatus.REGISTERED.value,
        )


@dataclass(slots=True)
class ThreadedChatDeletionDispatcher:
    """チャット物理削除を別スレッドへ登録するdispatcher。"""

    executor: ChatDeletionExecutorLike
    max_workers: int = 2
    _registered_chat_ids: set[UUID] = field(default_factory=set)
    _thread_pool: ThreadPoolExecutor = field(init=False)

    def __post_init__(self) -> None:
        self._thread_pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="d-concierge-chat-delete",
        )

    def dispatch_chat_deletion(
        self,
        chat_id: UUID,
        trace_id: str,
    ) -> ChatDeletionDispatchResult:
        if chat_id in self._registered_chat_ids:
            return ChatDeletionDispatchResult(
                status=ChatDeletionDispatchStatus.ALREADY_REGISTERED.value,
            )
        try:
            self._thread_pool.submit(self.executor.execute, chat_id, trace_id)
        except RuntimeError as error:
            return ChatDeletionDispatchResult(
                status=ChatDeletionDispatchStatus.FAILED.value,
                diagnostic_message=str(error),
            )
        self._registered_chat_ids.add(chat_id)
        return ChatDeletionDispatchResult(
            status=ChatDeletionDispatchStatus.REGISTERED.value,
        )


@dataclass(frozen=True, slots=True)
class DatabaseChatDeletionExecutor:
    """DBセッションを開き、チャット物理削除ユースケースを組み立てる。"""

    session_factory: sessionmaker[Session]
    settings: AppSettings
    trace_log_writer: TraceLogWriter
    cancel_requester: RunCancelRequesterLike

    def execute(self, chat_id: UUID, trace_id: str) -> None:
        saved_artifacts_dir = _saved_artifacts_dir(self.settings)
        with self.session_factory() as session:
            use_case = ExecuteChatDeletionUseCase(
                repository=SqlAlchemyChatRepository(session),
                cancel_requester=self.cancel_requester,
                workdir_cleanup=CodexSessionWorkdirCleanup(
                    self.settings.generator.workdir,
                    self.settings.validator.workdir,
                ),
                artifact_deletion=FileArtifactStore(saved_artifacts_dir),
                trace_logger=self.trace_log_writer,
            )
            use_case.execute(
                ExecuteChatDeletionCommand(
                    chat_id=chat_id,
                    trace_id=TraceId(trace_id),
                ),
            )


def _saved_artifacts_dir(settings: AppSettings) -> Path:
    saved_artifacts_dir = settings.generator.saved_artifacts_dir
    if saved_artifacts_dir is None:
        raise RuntimeError("generator.saved_artifacts_dir が未設定です。")
    return saved_artifacts_dir

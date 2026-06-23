from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from backend.application.account.execute_account_deletion import (
    ExecuteAccountDeletionCommand,
    ExecuteAccountDeletionUseCase,
)
from backend.application.ports.runtime.interface import (
    AccountDeletionDispatchResult,
    AccountDeletionDispatchStatus,
)
from backend.infrastructure.codex.session_workdir_cleanup import (
    CodexSessionWorkdirCleanup,
)
from backend.infrastructure.config.settings import AppSettings
from backend.infrastructure.database.repositories.account import (
    SqlAlchemyAccountRepository,
)
from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
from backend.infrastructure.runtime.codex_run_cancel_requester import (
    RunCancelRequesterLike,
)
from backend.infrastructure.trace_log.writer import TraceLogWriter
from backend.shared.tracing.trace_id import TraceId


class AccountDeletionExecutorLike(Protocol):
    """dispatcherから呼び出すアカウント物理削除本体。"""

    def execute(self, user_id: str, trace_id: str) -> None: ...


class NullAccountDeletionDispatcher:
    """F002で物理削除を起動しない削除ジョブ登録境界。"""

    def dispatch_account_deletion(
        self,
        user_id: str,
        trace_id: str,
    ) -> AccountDeletionDispatchResult:
        return AccountDeletionDispatchResult(
            status=AccountDeletionDispatchStatus.REGISTERED.value,
        )


@dataclass(slots=True)
class ThreadedAccountDeletionDispatcher:
    """アカウント物理削除を別スレッドへ登録するdispatcher。"""

    executor: AccountDeletionExecutorLike
    max_workers: int = 2
    _registered_user_ids: set[str] = field(default_factory=set)
    _thread_pool: ThreadPoolExecutor = field(init=False)

    def __post_init__(self) -> None:
        self._thread_pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="d-concierge-account-delete",
        )

    def dispatch_account_deletion(
        self,
        user_id: str,
        trace_id: str,
    ) -> AccountDeletionDispatchResult:
        if user_id in self._registered_user_ids:
            return AccountDeletionDispatchResult(
                status=AccountDeletionDispatchStatus.ALREADY_REGISTERED.value,
            )
        try:
            self._thread_pool.submit(self.executor.execute, user_id, trace_id)
        except RuntimeError as error:
            return AccountDeletionDispatchResult(
                status=AccountDeletionDispatchStatus.FAILED.value,
                diagnostic_message=str(error),
            )
        self._registered_user_ids.add(user_id)
        return AccountDeletionDispatchResult(
            status=AccountDeletionDispatchStatus.REGISTERED.value,
        )


@dataclass(frozen=True, slots=True)
class DatabaseAccountDeletionExecutor:
    """DBセッションを開き、アカウント物理削除ユースケースを組み立てる。"""

    session_factory: sessionmaker[Session]
    settings: AppSettings
    trace_log_writer: TraceLogWriter
    cancel_requester: RunCancelRequesterLike

    def execute(self, user_id: str, trace_id: str) -> None:
        saved_artifacts_dir = _saved_artifacts_dir(self.settings)
        with self.session_factory() as session:
            use_case = ExecuteAccountDeletionUseCase(
                repository=SqlAlchemyAccountRepository(session),
                cancel_requester=self.cancel_requester,
                workdir_cleanup=CodexSessionWorkdirCleanup(
                    self.settings.generator.workdir,
                    self.settings.validator.workdir,
                ),
                artifact_deletion=FileArtifactStore(saved_artifacts_dir),
                trace_logger=self.trace_log_writer,
            )
            use_case.execute(
                ExecuteAccountDeletionCommand(
                    user_id=user_id,
                    trace_id=TraceId(trace_id),
                ),
            )


def _saved_artifacts_dir(settings: AppSettings) -> Path:
    saved_artifacts_dir = settings.generator.saved_artifacts_dir
    if saved_artifacts_dir is None:
        raise RuntimeError("generator.saved_artifacts_dir が未設定です。")
    return saved_artifacts_dir

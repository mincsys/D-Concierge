from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from traceback import format_exception
from typing import Protocol
from uuid import UUID

from backend.application.ports.database.dto import AccountDeletionTarget
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId


class AccountDeletionRepositoryLike(Protocol):
    """アカウント物理削除で使うDB境界。"""

    def get_account_deletion_target(
        self,
        user_id: str,
    ) -> AccountDeletionTarget | None: ...

    def delete_account_data(self, user_id: str) -> None: ...


class CancelRequesterLike(Protocol):
    """未完了run終了要求境界。"""

    def cancel(self, run_id: UUID, trace_id: str) -> str: ...


class UserWorkdirCleanupLike(Protocol):
    """ユーザ単位Codex作業領域削除境界。"""

    def delete_user_workdirs(self, user_id: str) -> None: ...


class UserSavedArtifactDeletionLike(Protocol):
    """ユーザ単位保存済み成果物削除境界。"""

    def delete_user_saved_artifacts(self, user_id: str) -> None: ...


class TraceLoggerLike(Protocol):
    """TraceLogRecord保存境界。"""

    def write(self, record: TraceLogRecord) -> Path | None: ...


@dataclass(frozen=True, slots=True)
class ExecuteAccountDeletionCommand:
    """アカウント物理削除要求。"""

    user_id: str
    trace_id: TraceId


class ExecuteAccountDeletionUseCase:
    """アカウント物理削除を調停する。"""

    def __init__(
        self,
        *,
        repository: AccountDeletionRepositoryLike,
        cancel_requester: CancelRequesterLike,
        workdir_cleanup: UserWorkdirCleanupLike,
        artifact_deletion: UserSavedArtifactDeletionLike,
        trace_logger: TraceLoggerLike,
    ) -> None:
        self._repository = repository
        self._cancel_requester = cancel_requester
        self._workdir_cleanup = workdir_cleanup
        self._artifact_deletion = artifact_deletion
        self._trace_logger = trace_logger

    def execute(self, command: ExecuteAccountDeletionCommand) -> None:
        """ユーザ単位ファイル削除完了後にアカウント関連DBを削除する。"""

        target = self._repository.get_account_deletion_target(command.user_id)
        if target is None:
            return
        if target.unfinished_run_ids:
            for run_id in target.unfinished_run_ids:
                self._cancel_requester.cancel(run_id, str(command.trace_id))
            return

        try:
            self._workdir_cleanup.delete_user_workdirs(target.user_id)
            self._artifact_deletion.delete_user_saved_artifacts(target.user_id)
            self._repository.delete_account_data(target.user_id)
        except Exception as error:
            _write_trace_safely(
                self._trace_logger,
                TraceLogRecord(
                    occurred_at=datetime.now(UTC),
                    trace_id=command.trace_id,
                    event_name="account_physical_deletion_failed",
                    stage="application.account.execute_account_deletion",
                    error_type=ErrorType.SYSTEM,
                    message=str(error),
                    exception_type=type(error).__name__,
                    stacktrace="".join(
                        format_exception(type(error), error, error.__traceback__),
                    ),
                    http_method="",
                    path="background",
                    status_code=0,
                    user_id=target.user_id,
                ),
            )


def _write_trace_safely(
    trace_logger: TraceLoggerLike,
    record: TraceLogRecord,
) -> None:
    try:
        trace_logger.write(record)
    except Exception:
        return

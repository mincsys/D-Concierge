from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from traceback import format_exception
from typing import Protocol

from backend.application.ports.database.interface import TransactionManagerPort
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId


class AccountRecoveryRepositoryLike(Protocol):
    """起動時アカウント回復で使うDB境界。"""

    def delete_expired_sessions(self, now: datetime) -> int: ...

    def list_deleting_user_ids(self) -> tuple[str, ...]: ...


class ClockLike(Protocol):
    """現在時刻境界。"""

    def now_utc(self) -> datetime: ...


class TraceLoggerLike(Protocol):
    """TraceLogRecord保存境界。"""

    def write(self, record: TraceLogRecord) -> Path | None: ...


class DispatchResultLike(Protocol):
    """削除ジョブ登録結果の最小契約。"""

    @property
    def status(self) -> str: ...

    @property
    def diagnostic_message(self) -> str: ...


class AccountDeletionDispatcherLike(Protocol):
    """アカウント物理削除ジョブ登録境界。"""

    def dispatch_account_deletion(
        self,
        user_id: str,
        trace_id: str,
    ) -> DispatchResultLike: ...


@dataclass(frozen=True, slots=True)
class RecoverDeletingAccountsCommand:
    """起動時アカウント削除回復要求。"""

    trace_id: TraceId


@dataclass(frozen=True, slots=True)
class RecoverDeletingAccountsResult:
    """起動時アカウント削除回復結果。"""

    expired_sessions_deleted: int
    deleting_users_registered: int
    deleting_users_failed: int


class RecoverDeletingAccountsUseCase:
    """期限切れセッション削除とdeletingユーザの再登録を行う。"""

    def __init__(
        self,
        *,
        repository: AccountRecoveryRepositoryLike,
        transaction_manager: TransactionManagerPort,
        dispatcher: AccountDeletionDispatcherLike,
        trace_logger: TraceLoggerLike,
        clock: ClockLike,
    ) -> None:
        self._repository = repository
        self._transaction_manager = transaction_manager
        self._dispatcher = dispatcher
        self._trace_logger = trace_logger
        self._clock = clock

    def execute(
        self,
        command: RecoverDeletingAccountsCommand,
    ) -> RecoverDeletingAccountsResult:
        """起動時に期限切れセッションを削除し削除中ユーザを再登録する。"""

        expired_sessions_deleted = 0
        try:
            with self._transaction_manager:
                expired_sessions_deleted = self._repository.delete_expired_sessions(
                    self._clock.now_utc(),
                )
        except Exception as error:
            _write_recovery_exception(
                trace_logger=self._trace_logger,
                trace_id=command.trace_id,
                event_name="account_deletion_expired_session_cleanup_failed",
                message=f"期限切れセッション削除に失敗しました: {error}",
                error=error,
                user_id=None,
            )

        try:
            deleting_user_ids = self._repository.list_deleting_user_ids()
        except Exception as error:
            _write_recovery_exception(
                trace_logger=self._trace_logger,
                trace_id=command.trace_id,
                event_name="account_deletion_recovery_list_failed",
                message=f"削除中ユーザ一覧取得に失敗しました: {error}",
                error=error,
                user_id=None,
            )
            return RecoverDeletingAccountsResult(
                expired_sessions_deleted=expired_sessions_deleted,
                deleting_users_registered=0,
                deleting_users_failed=0,
            )

        registered_count = 0
        failed_count = 0
        for user_id in deleting_user_ids:
            try:
                result = self._dispatcher.dispatch_account_deletion(
                    user_id,
                    str(command.trace_id),
                )
            except Exception as error:
                failed_count += 1
                _write_recovery_exception(
                    trace_logger=self._trace_logger,
                    trace_id=command.trace_id,
                    event_name="account_deletion_recovery_failed",
                    message=f"アカウント削除ジョブ登録中に例外が発生しました: {error}",
                    error=error,
                    user_id=user_id,
                )
                continue
            if result.status == "failed":
                failed_count += 1
                _write_trace_safely(
                    self._trace_logger,
                    TraceLogRecord(
                        occurred_at=datetime.now(UTC),
                        trace_id=command.trace_id,
                        event_name="account_deletion_recovery_failed",
                        stage="application.account.recover_deleting_accounts",
                        error_type=ErrorType.SYSTEM,
                        message=result.diagnostic_message,
                        exception_type="AccountDeletionDispatchFailed",
                        stacktrace="",
                        http_method="",
                        path="startup",
                        status_code=0,
                        user_id=user_id,
                    ),
                )
                continue
            registered_count += 1

        return RecoverDeletingAccountsResult(
            expired_sessions_deleted=expired_sessions_deleted,
            deleting_users_registered=registered_count,
            deleting_users_failed=failed_count,
        )


def _write_recovery_exception(
    *,
    trace_logger: TraceLoggerLike,
    trace_id: TraceId,
    event_name: str,
    message: str,
    error: Exception,
    user_id: str | None,
) -> None:
    _write_trace_safely(
        trace_logger,
        TraceLogRecord(
            occurred_at=datetime.now(UTC),
            trace_id=trace_id,
            event_name=event_name,
            stage="application.account.recover_deleting_accounts",
            error_type=ErrorType.SYSTEM,
            message=message,
            exception_type=type(error).__name__,
            stacktrace="".join(
                format_exception(type(error), error, error.__traceback__),
            ),
            http_method="",
            path="startup",
            status_code=0,
            user_id=user_id,
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

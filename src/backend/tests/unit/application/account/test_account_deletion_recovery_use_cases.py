from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from backend.application.ports.database.dto import AccountDeletionTarget
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId

FIXED_NOW = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
TRACE_ID_VALUE = "018fe2d4-0000-7000-8000-000000000017"
USER_ID = "user-001"
RUN_ID = UUID("11111111-1111-7111-8111-111111111111")
SESSION_ID = UUID("22222222-2222-7222-8222-222222222222")


@dataclass(frozen=True, slots=True)
class DispatchResultRecord:
    status: str
    diagnostic_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelRequestRecord:
    run_id: UUID
    trace_id: str


@dataclass(slots=True)
class FixedClock:
    now: datetime = FIXED_NOW

    def now_utc(self) -> datetime:
        return self.now

    def now_app_timezone(self) -> datetime:
        return self.now


@dataclass(slots=True)
class FakeTransactionManager:
    begin_count: int = 0
    commit_count: int = 0
    rollback_count: int = 0

    def __enter__(self) -> None:
        self.begin_count += 1

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if exc_type is None:
            self.commit_count += 1
        else:
            self.rollback_count += 1
        return None


@dataclass(slots=True)
class FakeAccountDeletionRepository:
    deletion_target: AccountDeletionTarget | None = None
    deleting_user_ids: tuple[str, ...] = ()
    expire_error: Exception | None = None
    list_error: Exception | None = None
    target_requests: list[str] = field(default_factory=list)
    deleted_account_user_ids: list[str] = field(default_factory=list)
    expired_session_cleanup_times: list[datetime] = field(default_factory=list)

    def get_account_deletion_target(
        self,
        user_id: str,
    ) -> AccountDeletionTarget | None:
        self.target_requests.append(user_id)
        return self.deletion_target

    def delete_account_data(self, user_id: str) -> None:
        self.deleted_account_user_ids.append(user_id)

    def delete_expired_sessions(self, now: datetime) -> int:
        if self.expire_error is not None:
            raise self.expire_error
        self.expired_session_cleanup_times.append(now)
        return 2

    def list_deleting_user_ids(self) -> tuple[str, ...]:
        if self.list_error is not None:
            raise self.list_error
        return self.deleting_user_ids


@dataclass(slots=True)
class FakeCancelRequester:
    requests: list[CancelRequestRecord] = field(default_factory=list)

    def cancel(self, run_id: UUID, trace_id: str) -> str:
        self.requests.append(CancelRequestRecord(run_id=run_id, trace_id=trace_id))
        return "requested"


@dataclass(slots=True)
class FakeSessionWorkdirCleanup:
    deleted_user_ids: list[str] = field(default_factory=list)
    fail: bool = False

    def delete_user_workdirs(self, user_id: str) -> None:
        if self.fail:
            raise RuntimeError("user workdir deletion failed")
        self.deleted_user_ids.append(user_id)


@dataclass(slots=True)
class FakeSavedArtifactDeletion:
    deleted_user_ids: list[str] = field(default_factory=list)
    fail: bool = False

    def delete_user_saved_artifacts(self, user_id: str) -> None:
        if self.fail:
            raise RuntimeError("user artifact deletion failed")
        self.deleted_user_ids.append(user_id)


@dataclass(slots=True)
class FakeAccountDeletionDispatcher:
    next_results: dict[str, DispatchResultRecord] = field(default_factory=dict)
    exceptions: dict[str, Exception] = field(default_factory=dict)
    dispatched: list[tuple[str, str]] = field(default_factory=list)

    def dispatch_account_deletion(
        self,
        user_id: str,
        trace_id: str,
    ) -> DispatchResultRecord:
        self.dispatched.append((user_id, trace_id))
        if user_id in self.exceptions:
            raise self.exceptions[user_id]
        return self.next_results.get(user_id, DispatchResultRecord(status="registered"))


@dataclass(slots=True)
class FakeTraceLogger:
    records: list[TraceLogRecord] = field(default_factory=list)

    def write(self, record: TraceLogRecord) -> None:
        self.records.append(record)


def test_execute_account_deletion_defers_files_when_run_unfinished() -> None:
    """
    観点：アカウント物理削除ユースケースが未完了runの残るユーザを物理削除しないこと
    確認：未完了runへキャンセル要求し、ユーザ単位作業領域、保存済み成果物、
    DBデータ削除へ進まず、deletingユーザを再試行可能に残すこと
    """
    from backend.application.account.execute_account_deletion import (
        ExecuteAccountDeletionCommand,
        ExecuteAccountDeletionUseCase,
    )

    repository = FakeAccountDeletionRepository(
        deletion_target=_account_deletion_target(unfinished_run_ids=(RUN_ID,)),
    )
    cancel_requester = FakeCancelRequester()
    workdir_cleanup = FakeSessionWorkdirCleanup()
    artifact_deletion = FakeSavedArtifactDeletion()
    use_case = ExecuteAccountDeletionUseCase(
        repository=repository,
        cancel_requester=cancel_requester,
        workdir_cleanup=workdir_cleanup,
        artifact_deletion=artifact_deletion,
        trace_logger=FakeTraceLogger(),
    )

    use_case.execute(
        ExecuteAccountDeletionCommand(
            user_id=USER_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert cancel_requester.requests == [
        CancelRequestRecord(run_id=RUN_ID, trace_id=TRACE_ID_VALUE)
    ]
    assert workdir_cleanup.deleted_user_ids == []
    assert artifact_deletion.deleted_user_ids == []
    assert repository.deleted_account_user_ids == []


def test_execute_account_deletion_deletes_user_files_before_database_data() -> None:
    """
    観点：アカウント物理削除ユースケースがユーザ単位ファイル削除後にDB削除すること
    確認：未完了runがなければ生成/検証作業領域、保存済み成果物、DBデータを削除し、
    トレースログを出力しないこと
    """
    from backend.application.account.execute_account_deletion import (
        ExecuteAccountDeletionCommand,
        ExecuteAccountDeletionUseCase,
    )

    repository = FakeAccountDeletionRepository(
        deletion_target=_account_deletion_target(unfinished_run_ids=()),
    )
    workdir_cleanup = FakeSessionWorkdirCleanup()
    artifact_deletion = FakeSavedArtifactDeletion()
    trace_logger = FakeTraceLogger()
    use_case = ExecuteAccountDeletionUseCase(
        repository=repository,
        cancel_requester=FakeCancelRequester(),
        workdir_cleanup=workdir_cleanup,
        artifact_deletion=artifact_deletion,
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteAccountDeletionCommand(
            user_id=USER_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert workdir_cleanup.deleted_user_ids == [USER_ID]
    assert artifact_deletion.deleted_user_ids == [USER_ID]
    assert repository.deleted_account_user_ids == [USER_ID]
    assert trace_logger.records == []


def test_execute_account_deletion_logs_file_failure_without_database_delete() -> None:
    """
    観点：アカウント物理削除のファイル削除失敗時にDB削除へ進まないこと
    確認：対象ユーザはdeletingのまま残し、trace_id、user_id、失敗段階を
    トレースログへ記録すること
    """
    from backend.application.account.execute_account_deletion import (
        ExecuteAccountDeletionCommand,
        ExecuteAccountDeletionUseCase,
    )

    repository = FakeAccountDeletionRepository(
        deletion_target=_account_deletion_target(unfinished_run_ids=()),
    )
    trace_logger = FakeTraceLogger()
    use_case = ExecuteAccountDeletionUseCase(
        repository=repository,
        cancel_requester=FakeCancelRequester(),
        workdir_cleanup=FakeSessionWorkdirCleanup(fail=True),
        artifact_deletion=FakeSavedArtifactDeletion(),
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteAccountDeletionCommand(
            user_id=USER_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert repository.deleted_account_user_ids == []
    assert len(trace_logger.records) == 1
    _assert_account_trace_record(
        trace_logger.records[0],
        event_name="account_physical_deletion_failed",
        stage="application.account.execute_account_deletion",
        user_id=USER_ID,
        message="user workdir deletion failed",
        exception_type="RuntimeError",
        stacktrace_required=True,
    )


def test_recover_deleting_accounts_dispatches_users_and_prunes_sessions() -> None:
    """
    観点：起動時アカウント回復ユースケースが期限切れセッション削除と
    deletingユーザの物理削除ジョブ再登録を行うこと
    確認：active復帰は行わず、registered/already_registeredは正常扱い、
    failedだけをトレースログへ記録して次のユーザへ進むこと
    """
    from backend.application.account.recover_deleting_accounts import (
        RecoverDeletingAccountsCommand,
        RecoverDeletingAccountsUseCase,
    )

    repository = FakeAccountDeletionRepository(
        deleting_user_ids=("user-001", "user-002", "user-003"),
    )
    dispatcher = FakeAccountDeletionDispatcher(
        next_results={
            "user-002": DispatchResultRecord(status="already_registered"),
            "user-003": DispatchResultRecord(
                status="failed",
                diagnostic_message="submit failed",
            ),
        },
    )
    trace_logger = FakeTraceLogger()
    use_case = RecoverDeletingAccountsUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        trace_logger=trace_logger,
        clock=FixedClock(),
    )

    result = use_case.execute(
        RecoverDeletingAccountsCommand(trace_id=TraceId(TRACE_ID_VALUE)),
    )

    assert result.expired_sessions_deleted == 2
    assert result.deleting_users_registered == 2
    assert result.deleting_users_failed == 1
    assert repository.expired_session_cleanup_times == [FIXED_NOW]
    assert dispatcher.dispatched == [
        ("user-001", TRACE_ID_VALUE),
        ("user-002", TRACE_ID_VALUE),
        ("user-003", TRACE_ID_VALUE),
    ]
    assert len(trace_logger.records) == 1
    _assert_account_trace_record(
        trace_logger.records[0],
        event_name="account_deletion_recovery_failed",
        stage="application.account.recover_deleting_accounts",
        user_id="user-003",
        message="submit failed",
        exception_type="AccountDeletionDispatchFailed",
        stacktrace_required=False,
    )


def test_recover_deleting_accounts_logs_expired_session_failure_and_continues() -> None:
    """
    観点：起動時アカウント回復が期限切れセッション削除失敗を起動停止へ伝播しないこと
    確認：削除失敗をトレースログへ記録し、deletingユーザの物理削除ジョブ登録へ進むこと
    """
    from backend.application.account.recover_deleting_accounts import (
        RecoverDeletingAccountsCommand,
        RecoverDeletingAccountsUseCase,
    )

    repository = FakeAccountDeletionRepository(
        deleting_user_ids=("user-001",),
        expire_error=RuntimeError("expired session cleanup failed"),
    )
    dispatcher = FakeAccountDeletionDispatcher()
    trace_logger = FakeTraceLogger()
    use_case = RecoverDeletingAccountsUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        trace_logger=trace_logger,
        clock=FixedClock(),
    )

    result = use_case.execute(
        RecoverDeletingAccountsCommand(trace_id=TraceId(TRACE_ID_VALUE)),
    )

    assert result.expired_sessions_deleted == 0
    assert result.deleting_users_registered == 1
    assert dispatcher.dispatched == [("user-001", TRACE_ID_VALUE)]
    assert len(trace_logger.records) == 1
    _assert_account_trace_record(
        trace_logger.records[0],
        event_name="account_deletion_expired_session_cleanup_failed",
        stage="application.account.recover_deleting_accounts",
        user_id="",
        message="expired session cleanup failed",
        exception_type="RuntimeError",
        stacktrace_required=True,
    )


def test_recover_deleting_accounts_logs_list_failure_and_stops_registration() -> None:
    """
    観点：起動時アカウント回復がdeletingユーザ一覧取得失敗を起動停止へ伝播しないこと
    確認：一覧取得失敗をトレースログへ記録し、削除ジョブ登録を行わずに戻ること
    """
    from backend.application.account.recover_deleting_accounts import (
        RecoverDeletingAccountsCommand,
        RecoverDeletingAccountsUseCase,
    )

    repository = FakeAccountDeletionRepository(
        list_error=RuntimeError("deleting user list failed"),
    )
    dispatcher = FakeAccountDeletionDispatcher()
    trace_logger = FakeTraceLogger()
    use_case = RecoverDeletingAccountsUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        trace_logger=trace_logger,
        clock=FixedClock(),
    )

    result = use_case.execute(
        RecoverDeletingAccountsCommand(trace_id=TraceId(TRACE_ID_VALUE)),
    )

    assert result.expired_sessions_deleted == 2
    assert result.deleting_users_registered == 0
    assert dispatcher.dispatched == []
    assert len(trace_logger.records) == 1
    _assert_account_trace_record(
        trace_logger.records[0],
        event_name="account_deletion_recovery_list_failed",
        stage="application.account.recover_deleting_accounts",
        user_id="",
        message="deleting user list failed",
        exception_type="RuntimeError",
        stacktrace_required=True,
    )


def test_recover_deleting_accounts_logs_dispatch_exception_and_continues() -> None:
    """
    観点：起動時アカウント回復がdispatcher例外を個別失敗として扱うこと
    確認：例外をトレースログへ記録し、後続のdeletingユーザ登録へ進むこと
    """
    from backend.application.account.recover_deleting_accounts import (
        RecoverDeletingAccountsCommand,
        RecoverDeletingAccountsUseCase,
    )

    repository = FakeAccountDeletionRepository(
        deleting_user_ids=("user-001", "user-002"),
    )
    dispatcher = FakeAccountDeletionDispatcher(
        exceptions={"user-001": RuntimeError("dispatcher crashed")},
    )
    trace_logger = FakeTraceLogger()
    use_case = RecoverDeletingAccountsUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        trace_logger=trace_logger,
        clock=FixedClock(),
    )

    result = use_case.execute(
        RecoverDeletingAccountsCommand(trace_id=TraceId(TRACE_ID_VALUE)),
    )

    assert result.deleting_users_registered == 1
    assert result.deleting_users_failed == 1
    assert dispatcher.dispatched == [
        ("user-001", TRACE_ID_VALUE),
        ("user-002", TRACE_ID_VALUE),
    ]
    assert len(trace_logger.records) == 1
    _assert_account_trace_record(
        trace_logger.records[0],
        event_name="account_deletion_recovery_failed",
        stage="application.account.recover_deleting_accounts",
        user_id="user-001",
        message="dispatcher crashed",
        exception_type="RuntimeError",
        stacktrace_required=True,
    )


def _account_deletion_target(
    *,
    unfinished_run_ids: tuple[UUID, ...],
) -> AccountDeletionTarget:
    return AccountDeletionTarget(
        user_id=USER_ID,
        unfinished_run_ids=unfinished_run_ids,
        active_chat_session_ids=(SESSION_ID,),
    )


def _assert_account_trace_record(
    record: TraceLogRecord,
    *,
    event_name: str,
    stage: str,
    user_id: str,
    message: str,
    exception_type: str,
    stacktrace_required: bool,
) -> None:
    assert record.event_name == event_name
    assert record.stage == stage
    assert record.error_type == ErrorType.SYSTEM
    assert record.trace_id == TraceId(TRACE_ID_VALUE)
    assert record.user_id == (user_id or None)
    assert record.chat_id is None
    assert message in record.message
    assert record.exception_type == exception_type
    if stacktrace_required:
        assert exception_type in record.stacktrace
    else:
        assert record.stacktrace == ""

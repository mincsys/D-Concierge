from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

import pytest

from backend.application.ports.database.dto import ChatDeletionTarget
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.shared.errors.error_type import ErrorType
from backend.shared.tracing.trace_id import TraceId

FIXED_NOW = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
TRACE_ID_VALUE = "018fe2d4-0000-7000-8000-000000000007"
USER_ID = "user-001"
CHAT_ID = UUID("11111111-1111-7111-8111-111111111111")
RUN_ID = UUID("22222222-2222-7222-8222-222222222222")
SESSION_ID = UUID("33333333-3333-7333-8333-333333333333")


@dataclass(frozen=True, slots=True)
class DispatchResultRecord:
    status: str
    diagnostic_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelRequestRecord:
    run_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class CleanupRecord:
    user_id: str
    session_id: UUID


@dataclass(frozen=True, slots=True)
class SavedArtifactDeletionRecord:
    storage_paths: tuple[str, ...]


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
class FakeChatDeletionRepository:
    mark_result: str | None = "deleting"
    deletion_target: ChatDeletionTarget | None = None
    deleting_chat_ids: tuple[UUID, ...] = ()
    marked: list[tuple[str, UUID, datetime]] = field(default_factory=list)
    target_requests: list[UUID] = field(default_factory=list)
    deleted_chat_ids: list[UUID] = field(default_factory=list)

    def mark_chat_deleting(
        self,
        user_id: str,
        chat_id: UUID,
        updated_at: datetime,
    ) -> str | None:
        self.marked.append((user_id, chat_id, updated_at))
        return self.mark_result

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget | None:
        self.target_requests.append(chat_id)
        return self.deletion_target

    def delete_chat_cascade(self, chat_id: UUID) -> None:
        self.deleted_chat_ids.append(chat_id)

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]:
        return self.deleting_chat_ids


@dataclass(slots=True)
class FakeChatDeletionDispatcher:
    next_result: DispatchResultRecord = field(
        default_factory=lambda: DispatchResultRecord(status="registered"),
    )
    next_results: dict[UUID, DispatchResultRecord] = field(default_factory=dict)
    exceptions: dict[UUID, Exception] = field(default_factory=dict)
    dispatched: list[tuple[UUID, str]] = field(default_factory=list)

    def dispatch_chat_deletion(
        self,
        chat_id: UUID,
        trace_id: str,
    ) -> DispatchResultRecord:
        self.dispatched.append((chat_id, trace_id))
        if chat_id in self.exceptions:
            raise self.exceptions[chat_id]
        return self.next_results.get(chat_id, self.next_result)


@dataclass(slots=True)
class FakeTraceLogger:
    records: list[TraceLogRecord] = field(default_factory=list)

    def write(self, record: TraceLogRecord) -> None:
        self.records.append(record)


@dataclass(slots=True)
class FakeCancelRequester:
    requests: list[CancelRequestRecord] = field(default_factory=list)

    def cancel(self, run_id: UUID, trace_id: str) -> str:
        self.requests.append(CancelRequestRecord(run_id=run_id, trace_id=trace_id))
        return "requested"


@dataclass(slots=True)
class FakeSessionWorkdirCleanup:
    deleted_sessions: list[CleanupRecord] = field(default_factory=list)
    fail: bool = False

    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None:
        if self.fail:
            raise RuntimeError("workdir deletion failed")
        self.deleted_sessions.append(
            CleanupRecord(user_id=user_id, session_id=session_id),
        )


@dataclass(slots=True)
class FakeSavedArtifactDeletion:
    deleted: list[SavedArtifactDeletionRecord] = field(default_factory=list)
    fail: bool = False

    def delete_saved_files(self, storage_paths: tuple[str, ...]) -> tuple[str, ...]:
        if self.fail:
            raise RuntimeError("artifact deletion failed")
        self.deleted.append(SavedArtifactDeletionRecord(storage_paths=storage_paths))
        return storage_paths


def test_delete_chat_use_case_marks_chat_deleting_and_dispatches_job() -> None:
    """
    観点：チャット削除受付ユースケースが所有者のチャットを削除中にし、
    物理削除ジョブを登録すること
    確認：Repository更新はトランザクション内で行われ、応答はchat_state=deleting、
    dispatcherにはchat_idとtrace_idが渡り、物理削除portは呼ばれないこと
    """
    from backend.application.chat.delete_chat import (
        DeleteChatCommand,
        DeleteChatUseCase,
    )

    repository = FakeChatDeletionRepository()
    transaction_manager = FakeTransactionManager()
    dispatcher = FakeChatDeletionDispatcher()
    trace_logger = FakeTraceLogger()
    use_case = DeleteChatUseCase(
        repository=repository,
        transaction_manager=transaction_manager,
        dispatcher=dispatcher,
        trace_logger=trace_logger,
        clock=FixedClock(),
    )

    result = use_case.execute(
        DeleteChatCommand(
            authenticated_user_id=USER_ID,
            chat_id=CHAT_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.chat_id == CHAT_ID
    assert result.chat_state == "deleting"
    assert repository.marked == [(USER_ID, CHAT_ID, FIXED_NOW)]
    assert transaction_manager.begin_count == 1
    assert transaction_manager.commit_count == 1
    assert dispatcher.dispatched == [(CHAT_ID, TRACE_ID_VALUE)]
    assert trace_logger.records == []
    assert repository.deleted_chat_ids == []


def test_delete_chat_use_case_logs_dispatch_failure_keeps_response() -> None:
    """
    観点：チャット削除ジョブ登録失敗が削除受付結果を取り消さないこと
    確認：dispatcher failedでもchat_state=deletingを返し、診断情報を
    トレースログへ保存して、状態をactiveへ戻さないこと
    """
    from backend.application.chat.delete_chat import (
        DeleteChatCommand,
        DeleteChatUseCase,
    )

    repository = FakeChatDeletionRepository()
    dispatcher = FakeChatDeletionDispatcher(
        next_result=DispatchResultRecord(
            status="failed",
            diagnostic_message="background submit failed",
        ),
    )
    trace_logger = FakeTraceLogger()
    use_case = DeleteChatUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        trace_logger=trace_logger,
        clock=FixedClock(),
    )

    result = use_case.execute(
        DeleteChatCommand(
            authenticated_user_id=USER_ID,
            chat_id=CHAT_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.chat_state == "deleting"
    assert dispatcher.dispatched == [(CHAT_ID, TRACE_ID_VALUE)]
    assert len(trace_logger.records) == 1
    _assert_chat_trace_record(
        trace_logger.records[0],
        event_name="chat_deletion_dispatch_failed",
        stage="application.chat.delete_chat",
        message="background submit failed",
        exception_type="ChatDeletionDispatchFailed",
        stacktrace_required=False,
    )


def test_delete_chat_use_case_rejects_missing_chat_without_dispatch() -> None:
    """
    観点：チャット削除受付ユースケースが所有者不一致または対象なしを
    削除受付済みにしないこと
    確認：NOT_FOUNDのAppErrorとなり、dispatcher登録とトレースログ出力を行わないこと
    """
    from backend.application.chat.delete_chat import (
        DeleteChatCommand,
        DeleteChatUseCase,
    )
    from backend.shared.errors.error_type import ErrorType
    from backend.shared.errors.errors import AppError

    repository = FakeChatDeletionRepository(mark_result=None)
    dispatcher = FakeChatDeletionDispatcher()
    trace_logger = FakeTraceLogger()
    use_case = DeleteChatUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        trace_logger=trace_logger,
        clock=FixedClock(),
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            DeleteChatCommand(
                authenticated_user_id=USER_ID,
                chat_id=CHAT_ID,
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert raised.value.error_type == ErrorType.NOT_FOUND
    assert dispatcher.dispatched == []
    assert trace_logger.records == []


def test_recover_deleting_chats_dispatches_all_and_logs_failed_result() -> None:
    """
    観点：起動時チャット削除回復がdeletingチャットを物理削除ジョブへ再登録すること
    確認：failedだけをトレースログへ記録し、後続チャットの登録を継続すること
    """
    from backend.application.chat.recover_deleting_chats import (
        RecoverDeletingChatsCommand,
        RecoverDeletingChatsUseCase,
    )

    failed_chat_id = UUID("44444444-4444-7444-8444-444444444444")
    registered_chat_id = UUID("55555555-5555-7555-8555-555555555555")
    repository = FakeChatDeletionRepository(
        deleting_chat_ids=(failed_chat_id, registered_chat_id),
    )
    dispatcher = FakeChatDeletionDispatcher(
        next_results={
            failed_chat_id: DispatchResultRecord(
                status="failed",
                diagnostic_message="chat recovery submit failed",
            ),
        },
    )
    trace_logger = FakeTraceLogger()
    use_case = RecoverDeletingChatsUseCase(
        repository=repository,
        dispatcher=dispatcher,
        trace_logger=trace_logger,
    )

    result = use_case.execute(
        RecoverDeletingChatsCommand(trace_id=TraceId(TRACE_ID_VALUE)),
    )

    assert result.deleting_chats_registered == 1
    assert result.deleting_chats_failed == 1
    assert dispatcher.dispatched == [
        (failed_chat_id, TRACE_ID_VALUE),
        (registered_chat_id, TRACE_ID_VALUE),
    ]
    assert len(trace_logger.records) == 1
    _assert_chat_trace_record(
        trace_logger.records[0],
        event_name="chat_deletion_recovery_failed",
        stage="application.chat.recover_deleting_chats",
        message="chat recovery submit failed",
        exception_type="ChatDeletionDispatchFailed",
        stacktrace_required=False,
        chat_id=failed_chat_id,
    )


def test_recover_deleting_chats_logs_dispatch_exception_and_continues() -> None:
    """
    観点：起動時チャット削除回復がdispatcher例外を個別失敗に閉じること
    確認：例外をトレースログへ記録し、次のdeletingチャット登録へ進むこと
    """
    from backend.application.chat.recover_deleting_chats import (
        RecoverDeletingChatsCommand,
        RecoverDeletingChatsUseCase,
    )

    failed_chat_id = UUID("66666666-6666-7666-8666-666666666666")
    registered_chat_id = UUID("77777777-7777-7777-8777-777777777777")
    repository = FakeChatDeletionRepository(
        deleting_chat_ids=(failed_chat_id, registered_chat_id),
    )
    dispatcher = FakeChatDeletionDispatcher(
        exceptions={failed_chat_id: RuntimeError("chat dispatcher crashed")},
    )
    trace_logger = FakeTraceLogger()
    use_case = RecoverDeletingChatsUseCase(
        repository=repository,
        dispatcher=dispatcher,
        trace_logger=trace_logger,
    )

    result = use_case.execute(
        RecoverDeletingChatsCommand(trace_id=TraceId(TRACE_ID_VALUE)),
    )

    assert result.deleting_chats_registered == 1
    assert result.deleting_chats_failed == 1
    assert dispatcher.dispatched == [
        (failed_chat_id, TRACE_ID_VALUE),
        (registered_chat_id, TRACE_ID_VALUE),
    ]
    assert len(trace_logger.records) == 1
    _assert_chat_trace_record(
        trace_logger.records[0],
        event_name="chat_deletion_recovery_failed",
        stage="application.chat.recover_deleting_chats",
        message="chat dispatcher crashed",
        exception_type="RuntimeError",
        stacktrace_required=True,
        chat_id=failed_chat_id,
    )


def test_execute_chat_deletion_defers_files_when_run_unfinished() -> None:
    """
    観点：チャット物理削除ユースケースが未完了runの残るチャットを物理削除しないこと
    確認：キャンセル要求だけを行い、作業領域、保存済み成果物、DBカスケード削除へ
    進まず、対象チャットをdeletingのまま再試行可能に残すこと
    """
    from backend.application.chat.delete_chat import (
        ExecuteChatDeletionCommand,
        ExecuteChatDeletionUseCase,
    )

    repository = FakeChatDeletionRepository(
        deletion_target=_chat_deletion_target(unfinished_run_ids=(RUN_ID,)),
    )
    cancel_requester = FakeCancelRequester()
    workdir_cleanup = FakeSessionWorkdirCleanup()
    artifact_deletion = FakeSavedArtifactDeletion()
    use_case = ExecuteChatDeletionUseCase(
        repository=repository,
        cancel_requester=cancel_requester,
        workdir_cleanup=workdir_cleanup,
        artifact_deletion=artifact_deletion,
        trace_logger=FakeTraceLogger(),
    )

    use_case.execute(
        ExecuteChatDeletionCommand(
            chat_id=CHAT_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert cancel_requester.requests == [
        CancelRequestRecord(run_id=RUN_ID, trace_id=TRACE_ID_VALUE)
    ]
    assert workdir_cleanup.deleted_sessions == []
    assert artifact_deletion.deleted == []
    assert repository.deleted_chat_ids == []


def test_execute_chat_deletion_deletes_files_before_database_cascade() -> None:
    """
    観点：チャット物理削除ユースケースがファイル実体削除後にDBカスケード削除すること
    確認：未完了runがなければセッション作業領域、保存済み成果物、DBの順で削除し、
    トレースログを出力しないこと
    """
    from backend.application.chat.delete_chat import (
        ExecuteChatDeletionCommand,
        ExecuteChatDeletionUseCase,
    )

    repository = FakeChatDeletionRepository(
        deletion_target=_chat_deletion_target(unfinished_run_ids=()),
    )
    workdir_cleanup = FakeSessionWorkdirCleanup()
    artifact_deletion = FakeSavedArtifactDeletion()
    trace_logger = FakeTraceLogger()
    use_case = ExecuteChatDeletionUseCase(
        repository=repository,
        cancel_requester=FakeCancelRequester(),
        workdir_cleanup=workdir_cleanup,
        artifact_deletion=artifact_deletion,
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteChatDeletionCommand(
            chat_id=CHAT_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert workdir_cleanup.deleted_sessions == [
        CleanupRecord(user_id=USER_ID, session_id=SESSION_ID)
    ]
    assert artifact_deletion.deleted == [
        SavedArtifactDeletionRecord(
            storage_paths=("user-001/session-001/report.md",),
        )
    ]
    assert repository.deleted_chat_ids == [CHAT_ID]
    assert trace_logger.records == []


def test_execute_chat_deletion_logs_artifact_failure_without_db_delete() -> None:
    """
    観点：保存済み成果物削除失敗時にDBカスケード削除へ進まないこと
    確認：対象チャットはdeletingのまま残し、trace_id、chat_id、失敗段階を
    トレースログへ記録すること
    """
    from backend.application.chat.delete_chat import (
        ExecuteChatDeletionCommand,
        ExecuteChatDeletionUseCase,
    )

    repository = FakeChatDeletionRepository(
        deletion_target=_chat_deletion_target(unfinished_run_ids=()),
    )
    trace_logger = FakeTraceLogger()
    use_case = ExecuteChatDeletionUseCase(
        repository=repository,
        cancel_requester=FakeCancelRequester(),
        workdir_cleanup=FakeSessionWorkdirCleanup(),
        artifact_deletion=FakeSavedArtifactDeletion(fail=True),
        trace_logger=trace_logger,
    )

    use_case.execute(
        ExecuteChatDeletionCommand(
            chat_id=CHAT_ID,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert repository.deleted_chat_ids == []
    assert len(trace_logger.records) == 1
    _assert_chat_trace_record(
        trace_logger.records[0],
        event_name="chat_physical_deletion_failed",
        stage="application.chat.execute_chat_deletion",
        message="artifact deletion failed",
        exception_type="RuntimeError",
        stacktrace_required=True,
    )


def _chat_deletion_target(
    *,
    unfinished_run_ids: tuple[UUID, ...],
) -> ChatDeletionTarget:
    return ChatDeletionTarget(
        chat_id=CHAT_ID,
        user_id=USER_ID,
        session_id=SESSION_ID,
        unfinished_run_ids=unfinished_run_ids,
        storage_paths=("user-001/session-001/report.md",),
    )


def _assert_chat_trace_record(
    record: TraceLogRecord,
    *,
    event_name: str,
    stage: str,
    message: str,
    exception_type: str,
    stacktrace_required: bool,
    chat_id: UUID = CHAT_ID,
) -> None:
    assert record.event_name == event_name
    assert record.stage == stage
    assert record.error_type == ErrorType.SYSTEM
    assert record.trace_id == TraceId(TRACE_ID_VALUE)
    assert record.chat_id == str(chat_id)
    assert record.user_id is None
    assert message in record.message
    assert record.exception_type == exception_type
    if stacktrace_required:
        assert exception_type in record.stacktrace
    else:
        assert record.stacktrace == ""

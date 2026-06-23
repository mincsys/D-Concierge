from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import NotRequired, TypedDict
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.shared.tracing.trace_id import TraceId
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    FIXED_CHAT_NOW,
    RUN_ID_VALUE,
    SESSION_ID_VALUE,
    SeededChatUser,
    insert_chat_run,
    metadata_table,
    seed_chat_user,
)
from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    create_foundation_config,
    foundation_test_database_url,
    prepare_foundation_database,
)

ANSWER_BLOCK_ID_VALUE = UUID("66666666-6666-7666-8666-666666666666")
REFERENCE_ID_VALUE = UUID("77777777-7777-7777-8777-777777777777")
ARTIFACT_ID_VALUE = UUID("88888888-8888-7888-8888-888888888888")
PDF_BYTES = b"%PDF-1.4\n% f007 reference\n%%EOF\n"
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'


class ErrorPayload(TypedDict):
    error: str
    message: str
    field_errors: NotRequired[dict[str, str]]


class PdfLocatorDbPayload(TypedDict):
    path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ChatDeletionDispatchResultRecord:
    status: str
    diagnostic_message: str = ""


@dataclass(slots=True)
class RecordingChatDeletionDispatcher:
    next_result: ChatDeletionDispatchResultRecord = field(
        default_factory=lambda: ChatDeletionDispatchResultRecord(status="registered"),
    )
    next_results: dict[UUID, ChatDeletionDispatchResultRecord] = field(
        default_factory=dict,
    )
    exceptions: dict[UUID, Exception] = field(default_factory=dict)
    dispatched: list[tuple[UUID, str]] = field(default_factory=list)

    def dispatch_chat_deletion(
        self,
        chat_id: UUID,
        trace_id: str,
    ) -> ChatDeletionDispatchResultRecord:
        self.dispatched.append((chat_id, trace_id))
        if chat_id in self.exceptions:
            raise self.exceptions[chat_id]
        return self.next_results.get(chat_id, self.next_result)


@dataclass(frozen=True, slots=True)
class AccountDeletionDispatchResultRecord:
    status: str
    diagnostic_message: str = ""


@dataclass(slots=True)
class RecordingAccountDeletionDispatcher:
    next_results: dict[str, AccountDeletionDispatchResultRecord] = field(
        default_factory=dict,
    )
    exceptions: dict[str, Exception] = field(default_factory=dict)
    dispatched: list[tuple[str, str]] = field(default_factory=list)

    def dispatch_account_deletion(
        self,
        user_id: str,
        trace_id: str,
    ) -> AccountDeletionDispatchResultRecord:
        self.dispatched.append((user_id, trace_id))
        if user_id in self.exceptions:
            raise self.exceptions[user_id]
        return self.next_results.get(
            user_id,
            AccountDeletionDispatchResultRecord(status="registered"),
        )


@dataclass(slots=True)
class NoopCancelRequester:
    canceled: list[tuple[UUID, str]] = field(default_factory=list)

    def cancel(self, run_id: UUID, trace_id: str) -> str:
        self.canceled.append((run_id, trace_id))
        return "not_registered"


@dataclass(frozen=True, slots=True)
class AccountDeletionDispatcherFactory:
    dispatcher: RecordingAccountDeletionDispatcher

    def __call__(self) -> RecordingAccountDeletionDispatcher:
        return self.dispatcher


@pytest.mark.asyncio
async def test_delete_chat_api_marks_deleting_and_excludes_from_normal_reads(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB チャット削除APIが認証、DB、削除ジョブ登録、通常操作除外を結合すること
    確認：202でchat_state=deletingを返し、対象チャットを履歴一覧と履歴詳細から
    除外し、ChatDeletionDispatcherへchat_idとtrace_idを渡すこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("10101010-1010-7101-8101-101010101010"),
        title="削除対象チャット",
        instruction="削除前の指示",
        run_state=RunState.COMPLETED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    dispatcher = RecordingChatDeletionDispatcher()
    app.state.chat_deletion_dispatcher = dispatcher

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        delete_response = await client.delete(f"/api/chats/{CHAT_ID_VALUE}")
        histories_response = await client.get("/api/chat-histories")
        detail_response = await client.get(f"/api/chats/{CHAT_ID_VALUE}")

    assert delete_response.status_code == 202
    assert delete_response.json() == {
        "chat_id": str(CHAT_ID_VALUE),
        "chat_state": ChatState.DELETING.value,
    }
    trace_id = delete_response.headers["x-trace-id"]
    assert dispatcher.dispatched == [(CHAT_ID_VALUE, trace_id)]
    assert histories_response.status_code == 200
    assert str(CHAT_ID_VALUE) not in histories_response.text
    assert detail_response.status_code == 409
    assert _chat_state(database_url, CHAT_ID_VALUE) == ChatState.DELETING.value
    assert tuple(files.trace_log_dir.glob("*/*.yaml")) == ()


@pytest.mark.asyncio
async def test_deleting_chat_rejects_append_sse_reference_and_artifact_apis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：削除中チャットが履歴以外の通常操作対象からも除外されること
    確認：継続指示、SSE、参照元PDF取得、Codex成果物取得が409共通エラーとなり、
    新しいrunやファイル本文を返さないこと
    """
    from backend.app.factory import create_app
    from backend.infrastructure.runtime.chat_deletion_dispatcher import (
        DatabaseChatDeletionExecutor,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/deleting.pdf",
        artifact_storage_path=storage_path,
        chat_state=ChatState.DELETING.value,
    )
    pdf_path = files.data_source_dir / "manual" / "deleting.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(PDF_BYTES)
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)

    def execute_noop(
        self: DatabaseChatDeletionExecutor,
        chat_id: UUID,
        trace_id: str,
    ) -> None:
        return

    monkeypatch.setattr(DatabaseChatDeletionExecutor, "execute", execute_noop)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        append_response = await client.post(
            f"/api/chats/{CHAT_ID_VALUE}/runs",
            json={"user_instruction": "削除中チャットへの継続"},
        )
        sse_response = await client.get(
            f"/api/chats/{CHAT_ID_VALUE}/runs/{RUN_ID_VALUE}/sse",
        )
        reference_response = await client.get(f"/api/references/{REFERENCE_ID_VALUE}")
        artifact_response = await client.get(f"/api/artifacts/{ARTIFACT_ID_VALUE}")

    _assert_error_without_body(append_response, 409, "conflict", PDF_BYTES)
    _assert_error_without_body(sse_response, 409, "conflict", PDF_BYTES)
    _assert_error_without_body(reference_response, 409, "conflict", PDF_BYTES)
    _assert_error_without_body(artifact_response, 409, "conflict", SVG_BYTES)
    assert _table_count(database_url, "chat_runs") == 1
    assert str(files.data_source_dir) not in reference_response.text
    assert storage_path not in artifact_response.text


@pytest.mark.asyncio
async def test_delete_chat_api_logs_dispatch_failure_but_keeps_deleting_state(
    tmp_path: Path,
) -> None:
    """
    観点：チャット削除ジョブ登録失敗が利用者向け削除受付を失敗にしないこと
    確認：dispatcher failedでも202とdeleting状態を維持し、trace_id、chat_id、
    診断メッセージをトレースログへ保存すること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("20202020-2020-7202-8202-202020202020"),
        title="登録失敗確認チャット",
        instruction="削除前の指示",
        run_state=RunState.COMPLETED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    app.state.chat_deletion_dispatcher = RecordingChatDeletionDispatcher(
        next_result=ChatDeletionDispatchResultRecord(
            status="failed",
            diagnostic_message="chat deletion submit failed",
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.delete(f"/api/chats/{CHAT_ID_VALUE}")

    assert response.status_code == 202
    assert response.json()["chat_state"] == ChatState.DELETING.value
    trace_id = response.headers["x-trace-id"]
    assert _chat_state(database_url, CHAT_ID_VALUE) == ChatState.DELETING.value
    trace_logs = tuple(files.trace_log_dir.glob("*/*.yaml"))
    assert len(trace_logs) == 1
    trace_text = trace_logs[0].read_text(encoding="utf-8")
    assert "chat_deletion_dispatch_failed" in trace_text
    assert trace_id in trace_text
    assert str(CHAT_ID_VALUE) in trace_text
    assert "chat deletion submit failed" in trace_text


@pytest.mark.asyncio
async def test_delete_chat_api_default_dispatcher_reaches_database_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：実アプリ構成のチャット削除dispatcherがDB executorへ接続されること
    確認：app.state差し替えなしのDELETEでThreaded dispatcherから
    DatabaseChatDeletionExecutor.executeへchat_idとtrace_idが渡ること
    """
    from backend.app.factory import create_app
    from backend.infrastructure.runtime.chat_deletion_dispatcher import (
        DatabaseChatDeletionExecutor,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("21212121-2121-7121-8121-212121212121"),
        title="実dispatcher確認チャット",
        instruction="削除前の指示",
        run_state=RunState.COMPLETED.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    reached = Event()
    calls: list[tuple[UUID, str]] = []

    def execute_spy(
        self: DatabaseChatDeletionExecutor,
        chat_id: UUID,
        trace_id: str,
    ) -> None:
        calls.append((chat_id, trace_id))
        reached.set()

    monkeypatch.setattr(DatabaseChatDeletionExecutor, "execute", execute_spy)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.delete(f"/api/chats/{CHAT_ID_VALUE}")

    assert response.status_code == 202
    trace_id = response.headers["x-trace-id"]
    assert reached.wait(timeout=3)
    assert calls == [(CHAT_ID_VALUE, trace_id)]
    assert _chat_state(database_url, CHAT_ID_VALUE) == ChatState.DELETING.value


@pytest.mark.asyncio
async def test_delete_account_api_default_dispatcher_reaches_database_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：実アプリ構成のアカウント削除dispatcherがDB executorへ接続されること
    確認：app.state差し替えなしのDELETEでThreaded dispatcherから
    DatabaseAccountDeletionExecutor.executeへuser_idとtrace_idが渡ること
    """
    from backend.app.factory import create_app
    from backend.infrastructure.runtime.account_deletion_dispatcher import (
        DatabaseAccountDeletionExecutor,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url, session_token="account-delete-token")
    files = create_foundation_config(tmp_path, database_url=database_url)
    reached = Event()
    calls: list[tuple[str, str]] = []

    def execute_spy(
        self: DatabaseAccountDeletionExecutor,
        user_id: str,
        trace_id: str,
    ) -> None:
        calls.append((user_id, trace_id))
        reached.set()

    monkeypatch.setattr(DatabaseAccountDeletionExecutor, "execute", execute_spy)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.delete("/api/account")

    assert response.status_code == 202
    trace_id = response.headers["x-trace-id"]
    assert reached.wait(timeout=3)
    assert calls == [(seeded.user_id, trace_id)]
    assert _user_state(database_url, seeded.user_id) == "deleting"


def test_startup_recovery_registers_deleting_chats_and_logs_failed_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：起動時実行回復がdeletingチャットをChatDeletionDispatcherへ再登録すること
    確認：登録失敗をトレースログへ残し、後続チャットの再登録へ進むこと
    """

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    failed_chat_id = UUID("01010101-0101-7101-8101-010101010101")
    registered_chat_id = UUID("02020202-0202-7202-8202-020202020202")
    _insert_recovery_chat(
        database_url,
        user_id=seeded.user_id,
        chat_id=failed_chat_id,
        run_id=UUID("03030303-0303-7303-8303-030303030303"),
        session_id=UUID("04040404-0404-7404-8404-040404040404"),
    )
    _insert_recovery_chat(
        database_url,
        user_id=seeded.user_id,
        chat_id=registered_chat_id,
        run_id=UUID("05050505-0505-7505-8505-050505050505"),
        session_id=UUID("06060606-0606-7606-8606-060606060606"),
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    dispatcher = RecordingChatDeletionDispatcher(
        next_results={
            failed_chat_id: ChatDeletionDispatchResultRecord(
                status="failed",
                diagnostic_message="startup chat deletion submit failed",
            ),
        },
    )

    import backend.app.factory as app_factory

    monkeypatch.setattr(
        app_factory,
        "create_chat_deletion_dispatcher",
        lambda *args: dispatcher,
    )
    app_factory.create_app(config_path=files.config_path, base_dir=tmp_path)

    trace_id = dispatcher.dispatched[0][1]
    assert dispatcher.dispatched == [
        (failed_chat_id, trace_id),
        (registered_chat_id, trace_id),
    ]
    trace_logs = tuple(files.trace_log_dir.glob("*/*.yaml"))
    assert len(trace_logs) == 1
    trace_text = trace_logs[0].read_text(encoding="utf-8")
    assert "chat_deletion_recovery_failed" in trace_text
    assert str(failed_chat_id) in trace_text
    assert "startup chat deletion submit failed" in trace_text


@pytest.mark.asyncio
async def test_startup_recovery_prunes_expired_sessions_and_keeps_deleting_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：起動時アカウント回復が期限切れセッション削除とdeletingユーザ再登録を行うこと
    確認：期限切れlogin_sessionsを起動時に削除し、deletingユーザをactiveへ戻さず、
    通常履歴一覧にも削除中チャットを表示しないこと
    """

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_deleting_user_with_expired_session(
        database_url,
        user_id="deleting-user-001",
        session_token="deleting-user-token-001",
    )
    already_registered_user = _seed_deleting_user_with_expired_session(
        database_url,
        user_id="deleting-user-002",
        session_token="deleting-user-token-002",
    )
    failed_user = _seed_deleting_user_with_expired_session(
        database_url,
        user_id="deleting-user-003",
        session_token="deleting-user-token-003",
    )
    insert_chat_run(
        database_url,
        user_id=seeded.user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("30303030-3030-7303-8303-303030303030"),
        title="削除中チャット",
        instruction="削除中の指示",
        run_state=RunState.COMPLETED.value,
        chat_state=ChatState.DELETING.value,
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    dispatcher = RecordingAccountDeletionDispatcher(
        next_results={
            already_registered_user.user_id: AccountDeletionDispatchResultRecord(
                status="already_registered",
            ),
            failed_user.user_id: AccountDeletionDispatchResultRecord(
                status="failed",
                diagnostic_message="startup account deletion submit failed",
            ),
        },
    )

    import backend.app.factory as app_factory

    monkeypatch.setattr(
        app_factory,
        "create_account_deletion_dispatcher",
        _dispatcher_factory(dispatcher),
        raising=False,
    )
    app = app_factory.create_app(config_path=files.config_path, base_dir=tmp_path)

    assert _login_session_count(database_url, seeded.user_id) == 0
    assert _login_session_count(database_url, already_registered_user.user_id) == 0
    assert _login_session_count(database_url, failed_user.user_id) == 0
    assert _user_state(database_url, seeded.user_id) == "deleting"
    assert len(dispatcher.dispatched) == 3
    trace_id = dispatcher.dispatched[0][1]
    assert dispatcher.dispatched == [
        (seeded.user_id, trace_id),
        (already_registered_user.user_id, trace_id),
        (failed_user.user_id, trace_id),
    ]
    trace_logs = tuple(files.trace_log_dir.glob("*/*.yaml"))
    assert len(trace_logs) == 1
    trace_text = trace_logs[0].read_text(encoding="utf-8")
    assert "account_deletion_recovery_failed" in trace_text
    assert failed_user.user_id in trace_text
    assert "startup account deletion submit failed" in trace_text
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        histories_response = await client.get("/api/chat-histories")

    assert histories_response.status_code == 401
    assert str(CHAT_ID_VALUE) not in histories_response.text


def test_startup_account_recovery_logs_expired_session_cleanup_failure_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：起動時アカウント回復が期限切れセッション削除失敗をtraceして継続すること
    確認：DB例外をトレースログへ保存し、deletingユーザのdispatcher登録へ進むこと
    """
    from sqlalchemy.exc import SQLAlchemyError

    from backend.infrastructure.database.repositories.account import (
        SqlAlchemyAccountRepository,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    deleting = _seed_deleting_user_with_expired_session(
        database_url,
        user_id="deleting-expire-failed",
        session_token="deleting-expire-failed-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    dispatcher = RecordingAccountDeletionDispatcher()

    def delete_expired_sessions_failed(
        self: SqlAlchemyAccountRepository,
        now: datetime,
    ) -> int:
        raise SQLAlchemyError("expired session cleanup failed")

    import backend.app.factory as app_factory

    monkeypatch.setattr(
        SqlAlchemyAccountRepository,
        "delete_expired_sessions",
        delete_expired_sessions_failed,
    )
    monkeypatch.setattr(
        app_factory,
        "create_account_deletion_dispatcher",
        _dispatcher_factory(dispatcher),
        raising=False,
    )
    app_factory.create_app(config_path=files.config_path, base_dir=tmp_path)

    assert dispatcher.dispatched == [(deleting.user_id, dispatcher.dispatched[0][1])]
    trace_text = _single_trace_text(files.trace_log_dir)
    assert "account_deletion_expired_session_cleanup_failed" in trace_text
    assert "expired session cleanup failed" in trace_text


def test_startup_account_recovery_logs_user_list_failure_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：起動時アカウント回復がdeletingユーザ一覧取得失敗をtraceして継続すること
    確認：DB例外をトレースログへ保存し、dispatcher登録なしでcreate_appが戻ること
    """
    from sqlalchemy.exc import SQLAlchemyError

    from backend.infrastructure.database.repositories.account import (
        SqlAlchemyAccountRepository,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    _seed_deleting_user_with_expired_session(
        database_url,
        user_id="deleting-list-failed",
        session_token="deleting-list-failed-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    dispatcher = RecordingAccountDeletionDispatcher()

    def list_deleting_user_ids_failed(
        self: SqlAlchemyAccountRepository,
    ) -> tuple[str, ...]:
        raise SQLAlchemyError("deleting user list failed")

    import backend.app.factory as app_factory

    monkeypatch.setattr(
        SqlAlchemyAccountRepository,
        "list_deleting_user_ids",
        list_deleting_user_ids_failed,
    )
    monkeypatch.setattr(
        app_factory,
        "create_account_deletion_dispatcher",
        _dispatcher_factory(dispatcher),
        raising=False,
    )
    app_factory.create_app(config_path=files.config_path, base_dir=tmp_path)

    assert dispatcher.dispatched == []
    trace_text = _single_trace_text(files.trace_log_dir)
    assert "account_deletion_recovery_list_failed" in trace_text
    assert "deleting user list failed" in trace_text


def test_startup_account_recovery_logs_dispatch_exception_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：起動時アカウント回復がdispatcher例外をtraceして後続ユーザへ進むこと
    確認：例外ユーザをdeletingのまま残し、次のdeletingユーザを登録すること
    """

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    failed_user = _seed_deleting_user_with_expired_session(
        database_url,
        user_id="deleting-dispatch-exception-1",
        session_token="deleting-dispatch-exception-token-1",
    )
    registered_user = _seed_deleting_user_with_expired_session(
        database_url,
        user_id="deleting-dispatch-exception-2",
        session_token="deleting-dispatch-exception-token-2",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    dispatcher = RecordingAccountDeletionDispatcher(
        exceptions={
            failed_user.user_id: RuntimeError("account dispatcher crashed"),
        },
    )

    import backend.app.factory as app_factory

    monkeypatch.setattr(
        app_factory,
        "create_account_deletion_dispatcher",
        _dispatcher_factory(dispatcher),
        raising=False,
    )
    app_factory.create_app(config_path=files.config_path, base_dir=tmp_path)

    trace_id = dispatcher.dispatched[0][1]
    assert dispatcher.dispatched == [
        (failed_user.user_id, trace_id),
        (registered_user.user_id, trace_id),
    ]
    assert _user_state(database_url, failed_user.user_id) == "deleting"
    trace_text = _single_trace_text(files.trace_log_dir)
    assert "account_deletion_recovery_failed" in trace_text
    assert failed_user.user_id in trace_text
    assert "account dispatcher crashed" in trace_text


def test_execute_chat_deletion_integrates_database_files_and_trace_log(
    tmp_path: Path,
) -> None:
    """
    観点：チャット物理削除が実Repository、実ファイル削除Port、TraceLogWriterを結合すること
    確認：未完了runがないdeletingチャットでは作業領域、保存済み成果物、DBデータを
    削除し、トレースログを出力しないこと
    """
    from backend.application.chat.delete_chat import (
        ExecuteChatDeletionCommand,
        ExecuteChatDeletionUseCase,
    )
    from backend.infrastructure.codex.session_workdir_cleanup import (
        CodexSessionWorkdirCleanup,
    )
    from backend.infrastructure.database.repositories.chat import (
        SqlAlchemyChatRepository,
    )
    from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
    from backend.infrastructure.trace_log.writer import TraceLogWriter

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/delete.pdf",
        artifact_storage_path=storage_path,
        chat_state=ChatState.DELETING.value,
    )
    generation_workdir = (
        files.generator_workdir / seeded.user_id / str(SESSION_ID_VALUE)
    )
    validation_workdir = (
        files.validator_workdir / seeded.user_id / str(SESSION_ID_VALUE)
    )
    generation_workdir.mkdir(parents=True)
    validation_workdir.mkdir(parents=True)
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            use_case = ExecuteChatDeletionUseCase(
                repository=SqlAlchemyChatRepository(session),
                cancel_requester=NoopCancelRequester(),
                workdir_cleanup=CodexSessionWorkdirCleanup(
                    files.generator_workdir,
                    files.validator_workdir,
                ),
                artifact_deletion=FileArtifactStore(files.saved_artifacts_dir),
                trace_logger=TraceLogWriter(
                    root_dir=files.trace_log_dir,
                    timezone="Asia/Tokyo",
                    retention_days=90,
                    max_files_per_day=1000,
                ),
            )
            use_case.execute(
                ExecuteChatDeletionCommand(
                    chat_id=CHAT_ID_VALUE,
                    trace_id=response_trace_id(),
                ),
            )
    finally:
        engine.dispose()

    assert not generation_workdir.exists()
    assert not validation_workdir.exists()
    assert not saved_file.exists()
    assert _table_count(database_url, "chats") == 0
    assert _table_count(database_url, "chat_runs") == 0
    assert tuple(files.trace_log_dir.glob("*/*.yaml")) == ()


def test_database_chat_deletion_executor_requests_cancel_for_unfinished_run(
    tmp_path: Path,
) -> None:
    """
    観点：実アプリ用チャット物理削除executorが未完了runへ終了要求を送ること
    確認：deletingチャットにrunning runが残る場合、注入されたキャンセル境界へ
    run_id/trace_idを渡し、ファイル削除とDB削除へ進まないこと
    """
    from backend.infrastructure.config.loader import ConfigLoader
    from backend.infrastructure.database.session.factory import create_session_factory
    from backend.infrastructure.runtime.chat_deletion_dispatcher import (
        DatabaseChatDeletionExecutor,
    )
    from backend.infrastructure.trace_log.writer import TraceLogWriter

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/delete-running.pdf",
        artifact_storage_path=f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg",
        chat_state=ChatState.DELETING.value,
        run_state=RunState.RUNNING.value,
    )
    cancel_requester = NoopCancelRequester()
    engine = create_engine(database_url)
    try:
        executor = DatabaseChatDeletionExecutor(
            session_factory=create_session_factory(engine),
            settings=ConfigLoader().load(files.config_path, tmp_path),
            trace_log_writer=TraceLogWriter(
                root_dir=files.trace_log_dir,
                timezone="Asia/Tokyo",
                retention_days=90,
                max_files_per_day=1000,
            ),
            cancel_requester=cancel_requester,
        )

        executor.execute(CHAT_ID_VALUE, str(response_trace_id()))
    finally:
        engine.dispose()

    assert cancel_requester.canceled == [(RUN_ID_VALUE, str(response_trace_id()))]
    assert _chat_state(database_url, CHAT_ID_VALUE) == ChatState.DELETING.value
    assert _table_count(database_url, "chats") == 1
    assert tuple(files.trace_log_dir.glob("*/*.yaml")) == ()


def test_execute_chat_deletion_logs_file_failure_and_keeps_deleting_db(
    tmp_path: Path,
) -> None:
    """
    観点：チャット物理削除のファイル境界失敗がDB削除を止めてトレースログに残ること
    確認：保存済み成果物storage_pathが安全検証で失敗した場合、チャットはdeletingのまま
    DBに残り、trace_id、chat_id、失敗内容をTraceLogWriterで保存すること
    """
    from backend.application.chat.delete_chat import (
        ExecuteChatDeletionCommand,
        ExecuteChatDeletionUseCase,
    )
    from backend.infrastructure.codex.session_workdir_cleanup import (
        CodexSessionWorkdirCleanup,
    )
    from backend.infrastructure.database.repositories.chat import (
        SqlAlchemyChatRepository,
    )
    from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
    from backend.infrastructure.trace_log.writer import TraceLogWriter

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/delete.pdf",
        artifact_storage_path="../escape.svg",
        chat_state=ChatState.DELETING.value,
    )

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            use_case = ExecuteChatDeletionUseCase(
                repository=SqlAlchemyChatRepository(session),
                cancel_requester=NoopCancelRequester(),
                workdir_cleanup=CodexSessionWorkdirCleanup(
                    files.generator_workdir,
                    files.validator_workdir,
                ),
                artifact_deletion=FileArtifactStore(files.saved_artifacts_dir),
                trace_logger=TraceLogWriter(
                    root_dir=files.trace_log_dir,
                    timezone="Asia/Tokyo",
                    retention_days=90,
                    max_files_per_day=1000,
                ),
            )
            use_case.execute(
                ExecuteChatDeletionCommand(
                    chat_id=CHAT_ID_VALUE,
                    trace_id=response_trace_id(),
                ),
            )
    finally:
        engine.dispose()

    assert _chat_state(database_url, CHAT_ID_VALUE) == ChatState.DELETING.value
    assert _table_count(database_url, "chats") == 1
    trace_logs = tuple(files.trace_log_dir.glob("*/*.yaml"))
    assert len(trace_logs) == 1
    trace_text = trace_logs[0].read_text(encoding="utf-8")
    assert "chat_physical_deletion_failed" in trace_text
    assert str(CHAT_ID_VALUE) in trace_text
    assert "../escape.svg" in trace_text


def test_execute_account_deletion_integrates_database_files_and_trace_log(
    tmp_path: Path,
) -> None:
    """
    観点：アカウント物理削除が実Repository、実ファイル削除Port、TraceLogWriterを結合すること
    確認：未完了runがないdeletingユーザではユーザ単位作業領域、保存済み成果物、
    ユーザ関連DBデータを削除し、トレースログを出力しないこと
    """
    from backend.application.account.execute_account_deletion import (
        ExecuteAccountDeletionCommand,
        ExecuteAccountDeletionUseCase,
    )
    from backend.infrastructure.codex.session_workdir_cleanup import (
        CodexSessionWorkdirCleanup,
    )
    from backend.infrastructure.database.repositories.account import (
        SqlAlchemyAccountRepository,
    )
    from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
    from backend.infrastructure.trace_log.writer import TraceLogWriter

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(
        database_url,
        user_id="deleting-account",
        session_token="deleting-account-token",
        user_state="deleting",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/delete.pdf",
        artifact_storage_path=storage_path,
        chat_state=ChatState.DELETING.value,
    )
    generation_user_dir = files.generator_workdir / seeded.user_id
    validation_user_dir = files.validator_workdir / seeded.user_id
    saved_user_dir = files.saved_artifacts_dir / seeded.user_id
    (generation_user_dir / str(SESSION_ID_VALUE)).mkdir(parents=True)
    (validation_user_dir / str(SESSION_ID_VALUE)).mkdir(parents=True)
    saved_file = files.saved_artifacts_dir / storage_path
    saved_file.parent.mkdir(parents=True)
    saved_file.write_bytes(SVG_BYTES)

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            use_case = ExecuteAccountDeletionUseCase(
                repository=SqlAlchemyAccountRepository(session),
                cancel_requester=NoopCancelRequester(),
                workdir_cleanup=CodexSessionWorkdirCleanup(
                    files.generator_workdir,
                    files.validator_workdir,
                ),
                artifact_deletion=FileArtifactStore(files.saved_artifacts_dir),
                trace_logger=TraceLogWriter(
                    root_dir=files.trace_log_dir,
                    timezone="Asia/Tokyo",
                    retention_days=90,
                    max_files_per_day=1000,
                ),
            )
            use_case.execute(
                ExecuteAccountDeletionCommand(
                    user_id=seeded.user_id,
                    trace_id=response_trace_id(),
                ),
            )
    finally:
        engine.dispose()

    assert not generation_user_dir.exists()
    assert not validation_user_dir.exists()
    assert not saved_user_dir.exists()
    assert _table_count(database_url, "users") == 0
    assert _table_count(database_url, "chats") == 0
    assert tuple(files.trace_log_dir.glob("*/*.yaml")) == ()


def test_database_account_deletion_executor_requests_cancel_for_unfinished_run(
    tmp_path: Path,
) -> None:
    """
    観点：実アプリ用アカウント物理削除executorが未完了runへ終了要求を送ること
    確認：deletingユーザにrunning runが残る場合、注入されたキャンセル境界へ
    run_id/trace_idを渡し、ユーザ単位ファイル削除とDB削除へ進まないこと
    """
    from backend.infrastructure.config.loader import ConfigLoader
    from backend.infrastructure.database.session.factory import create_session_factory
    from backend.infrastructure.runtime.account_deletion_dispatcher import (
        DatabaseAccountDeletionExecutor,
    )
    from backend.infrastructure.trace_log.writer import TraceLogWriter

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(
        database_url,
        user_id="deleting-account",
        session_token="deleting-account-token",
        user_state="deleting",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/account-delete-running.pdf",
        artifact_storage_path=f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg",
        chat_state=ChatState.DELETING.value,
        run_state=RunState.RUNNING.value,
    )
    cancel_requester = NoopCancelRequester()
    engine = create_engine(database_url)
    try:
        executor = DatabaseAccountDeletionExecutor(
            session_factory=create_session_factory(engine),
            settings=ConfigLoader().load(files.config_path, tmp_path),
            trace_log_writer=TraceLogWriter(
                root_dir=files.trace_log_dir,
                timezone="Asia/Tokyo",
                retention_days=90,
                max_files_per_day=1000,
            ),
            cancel_requester=cancel_requester,
        )

        executor.execute(seeded.user_id, str(response_trace_id()))
    finally:
        engine.dispose()

    assert cancel_requester.canceled == [(RUN_ID_VALUE, str(response_trace_id()))]
    assert _user_state(database_url, seeded.user_id) == "deleting"
    assert _table_count(database_url, "users") == 1
    assert _table_count(database_url, "chats") == 1
    assert tuple(files.trace_log_dir.glob("*/*.yaml")) == ()


def test_execute_account_deletion_logs_file_failure_and_keeps_deleting_db(
    tmp_path: Path,
) -> None:
    """
    観点：アカウント物理削除のファイル境界失敗がDB削除を止めてトレースログに残ること
    確認：保存済み成果物のユーザ単位削除が失敗した場合、ユーザとチャットはdeletingのまま
    DBに残り、trace_id、user_id、失敗内容をTraceLogWriterで保存すること
    """
    from backend.application.account.execute_account_deletion import (
        ExecuteAccountDeletionCommand,
        ExecuteAccountDeletionUseCase,
    )
    from backend.infrastructure.codex.session_workdir_cleanup import (
        CodexSessionWorkdirCleanup,
    )
    from backend.infrastructure.database.repositories.account import (
        SqlAlchemyAccountRepository,
    )
    from backend.infrastructure.filesystem.artifact_store import FileArtifactStore
    from backend.infrastructure.trace_log.writer import TraceLogWriter

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = seed_chat_user(
        database_url,
        user_id="deleting-account",
        session_token="deleting-account-token",
        user_state="deleting",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    storage_path = f"{seeded.user_id}/{SESSION_ID_VALUE}/{ARTIFACT_ID_VALUE}.svg"
    _seed_completed_delivery_chat(
        database_url,
        user_id=seeded.user_id,
        reference_path="manual/delete.pdf",
        artifact_storage_path=storage_path,
        chat_state=ChatState.DELETING.value,
    )
    (files.generator_workdir / seeded.user_id / str(SESSION_ID_VALUE)).mkdir(
        parents=True,
    )
    (files.validator_workdir / seeded.user_id / str(SESSION_ID_VALUE)).mkdir(
        parents=True,
    )
    saved_user_path = files.saved_artifacts_dir / seeded.user_id
    saved_user_path.parent.mkdir(parents=True, exist_ok=True)
    saved_user_path.write_bytes(SVG_BYTES)

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            use_case = ExecuteAccountDeletionUseCase(
                repository=SqlAlchemyAccountRepository(session),
                cancel_requester=NoopCancelRequester(),
                workdir_cleanup=CodexSessionWorkdirCleanup(
                    files.generator_workdir,
                    files.validator_workdir,
                ),
                artifact_deletion=FileArtifactStore(files.saved_artifacts_dir),
                trace_logger=TraceLogWriter(
                    root_dir=files.trace_log_dir,
                    timezone="Asia/Tokyo",
                    retention_days=90,
                    max_files_per_day=1000,
                ),
            )
            use_case.execute(
                ExecuteAccountDeletionCommand(
                    user_id=seeded.user_id,
                    trace_id=response_trace_id(),
                ),
            )
    finally:
        engine.dispose()

    assert saved_user_path.is_file()
    assert _user_state(database_url, seeded.user_id) == "deleting"
    assert _chat_state(database_url, CHAT_ID_VALUE) == ChatState.DELETING.value
    assert _table_count(database_url, "users") == 1
    assert _table_count(database_url, "chats") == 1
    assert _table_count(database_url, "artifacts") == 1
    trace_logs = tuple(files.trace_log_dir.glob("*/*.yaml"))
    assert len(trace_logs) == 1
    trace_text = trace_logs[0].read_text(encoding="utf-8")
    assert "account_physical_deletion_failed" in trace_text
    assert str(response_trace_id()) in trace_text
    assert seeded.user_id in trace_text
    assert "saved_artifacts" in trace_text


def _expire_login_sessions_for_user(
    database_url: str,
    *,
    user_id: str,
    expires_at: datetime,
) -> None:
    engine = create_engine(database_url)
    try:
        login_sessions = metadata_table(engine, "login_sessions")
        with engine.begin() as connection:
            connection.execute(
                login_sessions.update()
                .where(login_sessions.c.user_id == user_id)
                .values(
                    expires_at=expires_at,
                    updated_at=FIXED_CHAT_NOW,
                ),
            )
    finally:
        engine.dispose()


def _seed_deleting_user_with_expired_session(
    database_url: str,
    *,
    user_id: str,
    session_token: str,
) -> SeededChatUser:
    seeded = seed_chat_user(
        database_url,
        user_id=user_id,
        session_token=session_token,
        user_state="deleting",
    )
    _expire_login_sessions_for_user(
        database_url,
        user_id=seeded.user_id,
        expires_at=FIXED_CHAT_NOW - timedelta(minutes=1),
    )
    return seeded


def _dispatcher_factory(
    dispatcher: RecordingAccountDeletionDispatcher,
) -> AccountDeletionDispatcherFactory:
    return AccountDeletionDispatcherFactory(dispatcher=dispatcher)


def _insert_recovery_chat(
    database_url: str,
    *,
    user_id: str,
    chat_id: UUID,
    run_id: UUID,
    session_id: UUID,
) -> None:
    insert_chat_run(
        database_url,
        user_id=user_id,
        chat_id=chat_id,
        run_id=run_id,
        session_id=session_id,
        instruction_id=run_id,
        title=f"起動時再登録対象 {chat_id}",
        instruction="起動時に削除ジョブへ再登録する。",
        run_state=RunState.COMPLETED.value,
        chat_state=ChatState.DELETING.value,
    )


def _single_trace_text(trace_log_dir: Path) -> str:
    trace_logs = tuple(trace_log_dir.glob("*/*.yaml"))
    assert len(trace_logs) == 1
    return trace_logs[0].read_text(encoding="utf-8")


def _seed_completed_delivery_chat(
    database_url: str,
    *,
    user_id: str,
    reference_path: str,
    artifact_storage_path: str,
    chat_state: str,
    run_state: str = RunState.COMPLETED.value,
) -> None:
    insert_chat_run(
        database_url,
        user_id=user_id,
        chat_id=CHAT_ID_VALUE,
        run_id=RUN_ID_VALUE,
        session_id=SESSION_ID_VALUE,
        instruction_id=UUID("40404040-4040-7404-8404-404040404040"),
        title="F007削除対象チャット",
        instruction="削除境界を確認する。",
        run_state=run_state,
        chat_state=chat_state,
    )
    engine = create_engine(database_url)
    try:
        _insert_answer_block_reference_and_artifact(
            engine,
            run_id=RUN_ID_VALUE,
            reference_path=reference_path,
            artifact_storage_path=artifact_storage_path,
        )
    finally:
        engine.dispose()


def _insert_answer_block_reference_and_artifact(
    engine: Engine,
    *,
    run_id: UUID,
    reference_path: str,
    artifact_storage_path: str,
) -> None:
    answer_blocks = metadata_table(engine, "answer_blocks")
    references = metadata_table(engine, "references")
    artifacts = metadata_table(engine, "artifacts")
    locator: PdfLocatorDbPayload = {
        "path": reference_path,
        "page_start": 2,
        "page_end": 3,
    }
    with engine.begin() as connection:
        connection.execute(
            answer_blocks.insert().values(
                id=ANSWER_BLOCK_ID_VALUE,
                run_id=run_id,
                position=1,
                markdown=f"回答本文 ![図](/api/artifacts/{ARTIFACT_ID_VALUE})",
            ),
        )
        connection.execute(
            references.insert().values(
                id=REFERENCE_ID_VALUE,
                answer_block_id=ANSWER_BLOCK_ID_VALUE,
                position=1,
                source_type="pdf",
                label="資料A",
                locator=locator,
            ),
        )
        connection.execute(
            artifacts.insert().values(
                id=ARTIFACT_ID_VALUE,
                answer_block_id=ANSWER_BLOCK_ID_VALUE,
                mime_type="image/svg+xml",
                storage_path=artifact_storage_path,
                created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            ),
        )


def _chat_state(database_url: str, chat_id: UUID) -> str | None:
    engine = create_engine(database_url)
    try:
        chats = metadata_table(engine, "chats")
        with engine.connect() as connection:
            state = connection.scalar(
                select(chats.c.chat_state).where(chats.c.id == chat_id),
            )
    finally:
        engine.dispose()
    assert isinstance(state, str) or state is None
    return state


def _user_state(database_url: str, user_id: str) -> str | None:
    engine = create_engine(database_url)
    try:
        users = metadata_table(engine, "users")
        with engine.connect() as connection:
            state = connection.scalar(
                select(users.c.user_state).where(users.c.id == user_id),
            )
    finally:
        engine.dispose()
    assert isinstance(state, str) or state is None
    return state


def _table_count(database_url: str, table_name: str) -> int:
    engine = create_engine(database_url)
    try:
        table = metadata_table(engine, table_name)
        with engine.connect() as connection:
            count_value = connection.scalar(select(func.count()).select_from(table))
    finally:
        engine.dispose()
    assert isinstance(count_value, int)
    return count_value


def _login_session_count(database_url: str, user_id: str) -> int:
    engine = create_engine(database_url)
    try:
        login_sessions = metadata_table(engine, "login_sessions")
        with engine.connect() as connection:
            count_value = connection.scalar(
                select(func.count())
                .select_from(login_sessions)
                .where(login_sessions.c.user_id == user_id),
            )
    finally:
        engine.dispose()
    assert isinstance(count_value, int)
    return count_value


def _assert_error_without_body(
    response: Response,
    status_code: int,
    error: str,
    forbidden_body: bytes,
) -> None:
    assert response.status_code == status_code
    payload = _error_payload(response)
    assert payload["error"] == error
    assert forbidden_body not in response.content


def _error_payload(response: Response) -> ErrorPayload:
    payload = response.json()
    assert isinstance(payload, dict)
    assert isinstance(payload.get("error"), str)
    assert isinstance(payload.get("message"), str)
    return ErrorPayload(error=payload["error"], message=payload["message"])


def response_trace_id() -> TraceId:
    return TraceId("018fe2d4-0000-7000-8000-000000000027")

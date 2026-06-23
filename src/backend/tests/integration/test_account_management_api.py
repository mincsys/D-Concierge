from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.engine import Engine

from backend.application.ports.runtime.interface import AccountDeletionDispatchResult
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.infrastructure.runtime.account_deletion_dispatcher import (
    DatabaseAccountDeletionExecutor,
    ThreadedAccountDeletionDispatcher,
)
from backend.infrastructure.trace_log.writer import TraceLogWriter
from backend.tests.integration.test_auth_account_api import (
    _assert_expired_cookie,
    _error_payload,
    _insert_login_session,
    _metadata_table,
    _password_hash,
    _seed_account,
    _session_count,
    _session_token_hashes,
    _user_response_payload,
    _user_state,
)
from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    create_foundation_config,
    foundation_test_database_url,
    prepare_foundation_database,
)


@pytest.mark.asyncio
async def test_change_user_name_api_requires_auth_and_updates_user_name(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-15 ユーザ名変更APIが認証依存関係とDB更新を結合すること
    確認：Cookieなしは401、Cookieありは200で変更後user payloadを返し、
    users.user_nameだけを更新してセッションを維持すること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="valid-token")
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        unauthenticated = await client.patch(
            "/api/account/name",
            json={"user_name": "変更後利用者"},
        )
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.patch(
            "/api/account/name",
            json={"user_name": "変更後利用者"},
        )

    assert unauthenticated.status_code == 401
    assert _error_payload(unauthenticated.text)["error"] == "unauthorized"
    assert response.status_code == 200
    assert _user_response_payload(response.text)["user"] == {
        "user_id": seeded.user_id,
        "user_name": "変更後利用者",
    }

    engine = create_engine(database_url)
    try:
        assert _user_name(engine, seeded.user_id) == "変更後利用者"
        assert _password_hash(engine, seeded.user_id) == seeded.password_hash
        assert _session_count(engine, seeded.user_id) == 1
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_change_user_name_api_returns_field_errors_without_db_update(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-15 ユーザ名変更APIがユーザ名入力不正を項目別エラーにすること
    確認：user_nameのfield_errorsを返し、users.user_name、password_hash、
    login_sessionsを変更しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="valid-token")
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.patch(
            "/api/account/name",
            json={"user_name": ""},
        )

    assert response.status_code == 400
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "user_name" in payload["field_errors"]
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _user_name(engine, seeded.user_id) == seeded.user_name
        assert _password_hash(engine, seeded.user_id) == seeded.password_hash
        assert _session_count(engine, seeded.user_id) == 1
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_change_password_api_updates_hash_and_keeps_sessions(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-16 パスワード変更APIが現在パスワード検証とハッシュ更新を結合すること
    確認：204で本文なし、保存ハッシュは新パスワードで検証可能になり、
    現在セッションと他セッションは削除されないこと
    """
    from backend.app.factory import create_app
    from backend.infrastructure.security.password_hasher import PasslibPasswordHasher

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="current-token")
    other_token_hash = _insert_login_session(
        database_url,
        user_id=seeded.user_id,
        session_token="other-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.patch(
            "/api/account/password",
            json={
                "current_password": "current-password",
                "new_password": "new-password",
                "new_password_confirmation": "new-password",
            },
        )

    assert response.status_code == 204
    assert response.text == ""

    engine = create_engine(database_url)
    try:
        new_hash = _password_hash(engine, seeded.user_id)
        assert new_hash != seeded.password_hash
        assert PasslibPasswordHasher().verify_password("new-password", new_hash)
        assert _session_token_hashes(engine, seeded.user_id) == tuple(
            sorted((seeded.session_token_hash, other_token_hash)),
        )
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "current_password",
        "new_password",
        "new_password_confirmation",
        "expected_field",
    ),
    (
        ("wrong-password", "new-password", "new-password", "current_password"),
        ("current-password", "1234", "1234", "new_password"),
        ("current-password", "passwordあ", "passwordあ", "new_password"),
        (
            "current-password",
            "new-password",
            "mismatch-password",
            "new_password_confirmation",
        ),
    ),
)
async def test_change_password_api_returns_field_errors_without_hash_update(
    tmp_path: Path,
    current_password: str,
    new_password: str,
    new_password_confirmation: str,
    expected_field: str,
) -> None:
    """
    観点：IF-SB-16 パスワード変更APIの入力不正が項目別エラーへ変換されること
    確認：current_password、new_password、new_password_confirmationを
    独立したfield_errorsとして返し、保存済みpassword_hashを変更しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="current-token")
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.patch(
            "/api/account/password",
            json={
                "current_password": current_password,
                "new_password": new_password,
                "new_password_confirmation": new_password_confirmation,
            },
        )

    assert response.status_code == 400
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert expected_field in payload["field_errors"]
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _password_hash(engine, seeded.user_id) == seeded.password_hash
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_delete_account_api_marks_data_deleting_and_expires_cookie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：IF-SB-17 アカウント削除APIが削除受付のDB更新とCookie失効を結合すること
    確認：202でaccount_state=deletingを返し、ユーザとチャットをdeletingにし、
    対象ユーザの全セッションを削除してCookieを失効すること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="delete-token")
    _insert_login_session(
        database_url,
        user_id=seeded.user_id,
        session_token="other-token",
    )
    chat_id = UUID("11111111-1111-7111-8111-111111111111")
    _insert_chat(database_url, user_id=seeded.user_id, chat_id=chat_id)
    files = create_foundation_config(tmp_path, database_url=database_url)
    reached = Event()

    def execute_spy(
        self: DatabaseAccountDeletionExecutor,
        user_id: str,
        trace_id: str,
    ) -> None:
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
    assert response.json() == {"account_state": "deleting"}
    _assert_expired_cookie(response.headers["set-cookie"])
    assert reached.wait(timeout=3)

    engine = create_engine(database_url)
    try:
        assert _user_state(engine, seeded.user_id) == "deleting"
        assert _chat_state(engine, chat_id) == "deleting"
        assert _session_count(engine, seeded.user_id) == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_delete_account_api_keeps_deleting_when_dispatcher_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：IF-SB-17 アカウント削除受付APIが削除ジョブ登録失敗を受付維持へ閉じること
    確認：dispatcherがfailedを返しても202、account_state=deleting、全セッション削除、
    Cookie失効を維持し、trace_id、対象ユーザ、診断メッセージをトレースログへ保存すること
    """
    from backend.app.factory import create_app

    def dispatch_failed(
        self: ThreadedAccountDeletionDispatcher,
        user_id: str,
        trace_id: str,
    ) -> AccountDeletionDispatchResult:
        return AccountDeletionDispatchResult(
            status="failed",
            diagnostic_message=f"dispatch failed: {user_id}:{trace_id}",
        )

    monkeypatch.setattr(
        ThreadedAccountDeletionDispatcher,
        "dispatch_account_deletion",
        dispatch_failed,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="delete-token")
    _insert_login_session(
        database_url,
        user_id=seeded.user_id,
        session_token="other-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.delete("/api/account")

    assert response.status_code == 202
    assert response.json() == {"account_state": "deleting"}
    _assert_expired_cookie(response.headers["set-cookie"])
    trace_id = response.headers["x-trace-id"]

    engine = create_engine(database_url)
    try:
        assert _user_state(engine, seeded.user_id) == "deleting"
        assert _session_count(engine, seeded.user_id) == 0
    finally:
        engine.dispose()
    trace_logs = tuple(files.trace_log_dir.glob("*/*.yaml"))
    assert len(trace_logs) == 1
    trace_log_text = trace_logs[0].read_text(encoding="utf-8")
    assert "account_deletion_dispatch_failed" in trace_log_text
    assert trace_id in trace_log_text
    assert seeded.user_id in trace_log_text
    assert "dispatch failed:" in trace_log_text


@pytest.mark.asyncio
async def test_delete_account_api_keeps_response_when_trace_log_write_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：IF-SB-17 削除ジョブ登録失敗のトレースログ書込失敗が
    削除受付応答を上書きしないこと
    確認：TraceLogWriter.writeが例外を送出しても202、Cookie失効、deleting状態、
    全セッション削除が維持されること
    """
    from backend.app.factory import create_app

    def dispatch_failed(
        self: ThreadedAccountDeletionDispatcher,
        user_id: str,
        trace_id: str,
    ) -> AccountDeletionDispatchResult:
        return AccountDeletionDispatchResult(
            status="failed",
            diagnostic_message=f"dispatch failed: {user_id}:{trace_id}",
        )

    def write_failed(self: TraceLogWriter, record: TraceLogRecord) -> Path:
        raise RuntimeError("trace log write failed")

    monkeypatch.setattr(
        ThreadedAccountDeletionDispatcher,
        "dispatch_account_deletion",
        dispatch_failed,
    )
    monkeypatch.setattr(TraceLogWriter, "write", write_failed)

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="delete-token")
    _insert_login_session(
        database_url,
        user_id=seeded.user_id,
        session_token="other-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.delete("/api/account")

    assert response.status_code == 202
    assert response.json() == {"account_state": "deleting"}
    _assert_expired_cookie(response.headers["set-cookie"])
    assert tuple(files.trace_log_dir.glob("*/*.yaml")) == ()

    engine = create_engine(database_url)
    try:
        assert _user_state(engine, seeded.user_id) == "deleting"
        assert _session_count(engine, seeded.user_id) == 0
    finally:
        engine.dispose()


def _insert_chat(database_url: str, *, user_id: str, chat_id: UUID) -> None:
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine, only=("chats",))
        chats = metadata.tables["chats"]
        now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        with engine.begin() as connection:
            connection.execute(
                chats.insert().values(
                    id=chat_id,
                    user_id=user_id,
                    session_id=UUID("22222222-2222-7222-8222-222222222222"),
                    chat_state="active",
                    title="削除対象チャット",
                    generation_conversation_id=None,
                    validation_conversation_id=None,
                    updated_at=now,
                ),
            )
    finally:
        engine.dispose()


def _user_name(engine: Engine, user_id: str) -> str:
    users = _metadata_table(engine, "users")
    with engine.connect() as connection:
        user_name = connection.scalar(
            select(users.c.user_name).where(users.c.id == user_id),
        )
    assert isinstance(user_name, str)
    return user_name


def _chat_state(engine: Engine, chat_id: UUID) -> str:
    chats = _metadata_table(engine, "chats")
    with engine.connect() as connection:
        chat_state = connection.scalar(
            select(chats.c.chat_state).where(chats.c.id == chat_id),
        )
    assert isinstance(chat_state, str)
    return chat_state

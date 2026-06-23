from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NotRequired, TypedDict

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.engine import Engine

from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    create_foundation_config,
    foundation_test_database_url,
    prepare_foundation_database,
)


class UserPayload(TypedDict):
    user_id: str
    user_name: str


class UserResponsePayload(TypedDict):
    user: UserPayload


class FieldErrorsPayload(TypedDict, total=False):
    user_id: str
    user_name: str
    password: str
    password_confirmation: str
    current_password: str
    new_password: str
    new_password_confirmation: str


class ErrorResponsePayload(TypedDict):
    error: str
    message: str
    field_errors: NotRequired[FieldErrorsPayload]


@dataclass(frozen=True, slots=True)
class SeededAccount:
    user_id: str
    user_name: str
    password_hash: str
    session_token: str
    session_token_hash: str


@pytest.mark.asyncio
async def test_register_api_returns_user_cookie_and_persists_hashed_secrets(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-12 アカウント登録APIがapplication、security、DB、
    Cookie境界を結合すること
    確認：200でuser payloadとログインCookieを返し、DBにはactiveユーザ、
    パスワードハッシュ、token_hashだけが保存されること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "user_id": "user-001",
                "user_name": "利用者",
                "password": "raw-password",
                "password_confirmation": "raw-password",
            },
        )

    assert response.status_code == 200
    assert response.headers["x-trace-id"]
    payload = _user_response_payload(response.text)
    assert payload["user"] == {"user_id": "user-001", "user_name": "利用者"}
    _assert_login_cookie_attributes(response.headers["set-cookie"])
    session_token = response.cookies.get(LOGIN_SESSION_COOKIE_NAME)
    assert session_token is not None

    engine = create_engine(database_url)
    try:
        assert _user_state(engine, "user-001") == "active"
        assert _password_hash(engine, "user-001") != "raw-password"
        assert "raw-password" not in _password_hash(engine, "user-001")
        assert _session_count(engine, "user-001") == 1
        assert session_token not in _session_token_hashes(engine, "user-001")
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_register_api_returns_field_errors_without_db_write(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-12 アカウント登録APIの入力不正が項目別エラーへ変換されること
    確認：400とfield_errorsを返し、Set-Cookie、users、login_sessionsを作成しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "user_id": "-invalid",
                "user_name": "",
                "password": "1234",
                "password_confirmation": "mismatch",
            },
        )

    assert response.status_code == 400
    assert LOGIN_SESSION_COOKIE_NAME not in response.cookies
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert {"user_id", "user_name", "password", "password_confirmation"} <= set(
        payload["field_errors"],
    )
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _table_count(engine, "users") == 0
        assert _table_count(engine, "login_sessions") == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_register_api_rejects_unsupported_password_characters(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-12 アカウント登録APIがパスワード文字種制約をREST境界で守ること
    確認：全角文字を含むpasswordはfield_errors.passwordを返し、
    Set-Cookie、users、login_sessionsを作成しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "user_id": "user-001",
                "user_name": "利用者",
                "password": "passwordあ",
                "password_confirmation": "passwordあ",
            },
        )

    assert response.status_code == 400
    assert LOGIN_SESSION_COOKIE_NAME not in response.cookies
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "password" in payload["field_errors"]

    engine = create_engine(database_url)
    try:
        assert _table_count(engine, "users") == 0
        assert _table_count(engine, "login_sessions") == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_register_api_rejects_duplicate_user_id_without_cookie_or_db_change(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-12 アカウント登録APIが既存ユーザIDをREST境界で項目別エラーへ変換すること
    確認：400とfield_errors.user_idを返し、Set-Cookieを返さず、既存usersと
    login_sessionsを変更しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="existing-token")
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "user_id": seeded.user_id,
                "user_name": "別利用者",
                "password": "raw-password",
                "password_confirmation": "raw-password",
            },
        )

    assert response.status_code == 400
    assert LOGIN_SESSION_COOKIE_NAME not in response.cookies
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "user_id" in payload["field_errors"]
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _table_count(engine, "users") == 1
        assert _user_state(engine, seeded.user_id) == "active"
        assert _session_token_hashes(engine, seeded.user_id) == (
            seeded.session_token_hash,
        )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_login_api_replaces_existing_session_cookie(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-13 ログインAPIが認証成功時に既存Cookieセッションを置き換えること
    確認：200でuser payloadと新Cookieを返し、
    旧token_hashを削除して新token_hashだけを保存すること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="old-login-token")
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, seeded.session_token)
        response = await client.post(
            "/api/auth/login",
            json={
                "user_id": seeded.user_id,
                "password": "current-password",
            },
        )

    assert response.status_code == 200
    payload = _user_response_payload(response.text)
    assert payload["user"] == {
        "user_id": seeded.user_id,
        "user_name": seeded.user_name,
    }
    new_session_token = response.cookies.get(LOGIN_SESSION_COOKIE_NAME)
    assert new_session_token is not None
    assert new_session_token != seeded.session_token
    _assert_login_cookie_attributes(response.headers["set-cookie"])

    engine = create_engine(database_url)
    try:
        assert _session_count(engine, seeded.user_id) == 1
        token_hashes = _session_token_hashes(engine, seeded.user_id)
        assert seeded.session_token_hash not in token_hashes
        assert new_session_token not in token_hashes
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_login_api_returns_field_errors_without_session_creation(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-13 ログインAPIの認証失敗が項目別エラーへ変換されること
    確認：パスワード不一致はpasswordのfield_errorsを返し、新しいCookieとセッションを作成しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(database_url, session_token="existing-token")
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "user_id": seeded.user_id,
                "password": "wrong-password",
            },
        )

    assert response.status_code == 400
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "password" in payload["field_errors"]
    assert LOGIN_SESSION_COOKIE_NAME not in response.cookies
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _session_count(engine, seeded.user_id) == 1
        assert _session_token_hashes(engine, seeded.user_id) == (
            seeded.session_token_hash,
        )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_login_api_rejects_unknown_user_id_without_session_creation(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-13 ログインAPIが存在しないユーザIDを項目別エラーにすること
    確認：400とfield_errors.user_idを返し、Set-Cookie、users、login_sessionsを作成しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "user_id": "missing-user",
                "password": "current-password",
            },
        )

    assert response.status_code == 400
    assert LOGIN_SESSION_COOKIE_NAME not in response.cookies
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "user_id" in payload["field_errors"]
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _table_count(engine, "users") == 0
        assert _table_count(engine, "login_sessions") == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_login_api_rejects_deleting_user_without_session_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：IF-SB-13 ログインAPIが削除中ユーザを通常ログイン不可として扱うこと
    確認：400とfield_errors.user_idを返し、Set-Cookieを返さず、既存セッションだけを維持すること
    """
    from backend.app.factory import create_app
    from backend.infrastructure.runtime.account_deletion_dispatcher import (
        DatabaseAccountDeletionExecutor,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    seeded = _seed_account(
        database_url,
        user_name="削除中利用者",
        session_token="deleting-login-token",
        user_state="deleting",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)

    def execute_noop(
        self: DatabaseAccountDeletionExecutor,
        user_id: str,
        trace_id: str,
    ) -> None:
        return

    monkeypatch.setattr(DatabaseAccountDeletionExecutor, "execute", execute_noop)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "user_id": seeded.user_id,
                "password": "current-password",
            },
        )

    assert response.status_code == 400
    assert LOGIN_SESSION_COOKIE_NAME not in response.cookies
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert "user_id" in payload["field_errors"]
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _user_state(engine, seeded.user_id) == "deleting"
        assert _session_token_hashes(engine, seeded.user_id) == (
            seeded.session_token_hash,
        )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_auth_me_returns_user_and_deletes_expired_session(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-11 認証状態確認APIがセッション有効性とユーザ状態をDBで確認すること
    確認：有効セッションはuser payloadを返し、期限切れセッションは401にした上で
    対応するlogin_sessions行を削除すること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    valid = _seed_account(database_url, session_token="valid-token")
    expired = _seed_account(
        database_url,
        user_id="user-002",
        user_name="期限切れ利用者",
        session_token="expired-token",
        session_expires_at=datetime(2025, 12, 31, 23, 59, tzinfo=UTC),
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, valid.session_token)
        valid_response = await client.get("/api/auth/me")
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, expired.session_token)
        expired_response = await client.get("/api/auth/me")

    assert valid_response.status_code == 200
    assert _user_response_payload(valid_response.text)["user"] == {
        "user_id": valid.user_id,
        "user_name": valid.user_name,
    }
    assert expired_response.status_code == 401
    error_payload = _error_payload(expired_response.text)
    assert error_payload["error"] == "unauthorized"
    assert "detail" not in expired_response.text

    engine = create_engine(database_url)
    try:
        assert expired.session_token_hash not in _session_token_hashes(
            engine,
            expired.user_id,
        )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_auth_me_rejects_deleting_user_session_and_deletes_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：IF-SB-11 認証状態確認APIが削除中ユーザのセッションを未ログイン相当にすること
    確認：401と共通エラー形式を返し、該当login_sessions行を削除し、ユーザ状態は維持すること
    """
    from backend.app.factory import create_app
    from backend.infrastructure.runtime.account_deletion_dispatcher import (
        DatabaseAccountDeletionExecutor,
    )

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    deleting = _seed_account(
        database_url,
        user_name="削除中利用者",
        session_token="deleting-auth-token",
        user_state="deleting",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)

    def execute_noop(
        self: DatabaseAccountDeletionExecutor,
        user_id: str,
        trace_id: str,
    ) -> None:
        return

    monkeypatch.setattr(DatabaseAccountDeletionExecutor, "execute", execute_noop)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, deleting.session_token)
        response = await client.get("/api/auth/me")

    assert response.status_code == 401
    payload = _error_payload(response.text)
    assert payload["error"] == "unauthorized"
    assert "detail" not in response.text

    engine = create_engine(database_url)
    try:
        assert _user_state(engine, deleting.user_id) == "deleting"
        assert deleting.session_token_hash not in _session_token_hashes(
            engine,
            deleting.user_id,
        )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_logout_api_deletes_current_session_and_expires_cookie(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-14 ログアウトAPIが現在Cookieのセッションだけを終了すること
    確認：204でレスポンスボディを返さずCookieを失効し、
    対象token_hashだけを削除して他セッションを維持すること
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    current = _seed_account(database_url, session_token="current-token")
    other_token_hash = _insert_login_session(
        database_url,
        user_id=current.user_id,
        session_token="other-token",
    )
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, current.session_token)
        response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert response.text == ""
    _assert_expired_cookie(response.headers["set-cookie"])

    engine = create_engine(database_url)
    try:
        assert _session_token_hashes(engine, current.user_id) == (other_token_hash,)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_logout_api_without_cookie_still_expires_cookie(
    tmp_path: Path,
) -> None:
    """
    観点：IF-SB-14 ログアウトAPIがCookieなしでもログアウト済み確認として成功すること
    確認：204でレスポンスボディを返さずCookie失効ヘッダを返し、DB状態を変更しないこと
    """
    from backend.app.factory import create_app

    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    files = create_foundation_config(tmp_path, database_url=database_url)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert response.text == ""
    _assert_expired_cookie(response.headers["set-cookie"])

    engine = create_engine(database_url)
    try:
        assert _table_count(engine, "users") == 0
        assert _table_count(engine, "login_sessions") == 0
    finally:
        engine.dispose()


def _seed_account(
    database_url: str,
    *,
    user_id: str = "user-001",
    user_name: str = "利用者",
    password: str = "current-password",
    session_token: str,
    user_state: str = "active",
    session_expires_at: datetime | None = None,
) -> SeededAccount:
    from backend.infrastructure.security.password_hasher import PasslibPasswordHasher

    password_hash = PasslibPasswordHasher().hash_password(password)
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine, only=("users", "login_sessions"))
        users = metadata.tables["users"]
        now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        with engine.begin() as connection:
            connection.execute(
                users.insert().values(
                    id=user_id,
                    user_name=user_name,
                    password_hash=password_hash,
                    user_state=user_state,
                    created_at=now,
                    updated_at=now,
                ),
            )
        token_hash = _insert_login_session(
            database_url,
            user_id=user_id,
            session_token=session_token,
            expires_at=session_expires_at,
        )
    finally:
        engine.dispose()
    return SeededAccount(
        user_id=user_id,
        user_name=user_name,
        password_hash=password_hash,
        session_token=session_token,
        session_token_hash=token_hash,
    )


def _insert_login_session(
    database_url: str,
    *,
    user_id: str,
    session_token: str,
    expires_at: datetime | None = None,
) -> str:
    from backend.infrastructure.security.session_token import (
        SecretsSessionTokenProvider,
    )

    token_hash = SecretsSessionTokenProvider().hash_token(session_token)
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine, only=("login_sessions",))
        login_sessions = metadata.tables["login_sessions"]
        now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        with engine.begin() as connection:
            connection.execute(
                login_sessions.insert().values(
                    token_hash=token_hash,
                    user_id=user_id,
                    expires_at=expires_at or now + timedelta(days=400),
                    created_at=now,
                    updated_at=now,
                ),
            )
    finally:
        engine.dispose()
    return token_hash


def _metadata_table(engine: Engine, table_name: str) -> Table:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=(table_name,))
    return metadata.tables[table_name]


def _table_count(engine: Engine, table_name: str) -> int:
    table = _metadata_table(engine, table_name)
    with engine.connect() as connection:
        count_value = connection.scalar(select(func.count()).select_from(table))
    assert isinstance(count_value, int)
    return count_value


def _user_state(engine: Engine, user_id: str) -> str:
    users = _metadata_table(engine, "users")
    with engine.connect() as connection:
        state = connection.scalar(
            select(users.c.user_state).where(users.c.id == user_id),
        )
    assert isinstance(state, str)
    return state


def _password_hash(engine: Engine, user_id: str) -> str:
    users = _metadata_table(engine, "users")
    with engine.connect() as connection:
        password_hash = connection.scalar(
            select(users.c.password_hash).where(users.c.id == user_id),
        )
    assert isinstance(password_hash, str)
    return password_hash


def _session_count(engine: Engine, user_id: str) -> int:
    login_sessions = _metadata_table(engine, "login_sessions")
    with engine.connect() as connection:
        count_value = connection.scalar(
            select(func.count())
            .select_from(login_sessions)
            .where(login_sessions.c.user_id == user_id),
        )
    assert isinstance(count_value, int)
    return count_value


def _session_token_hashes(engine: Engine, user_id: str) -> tuple[str, ...]:
    login_sessions = _metadata_table(engine, "login_sessions")
    with engine.connect() as connection:
        rows = connection.execute(
            select(login_sessions.c.token_hash)
            .where(login_sessions.c.user_id == user_id)
            .order_by(login_sessions.c.token_hash),
        )
    return tuple(str(row[0]) for row in rows)


def _user_response_payload(response_text: str) -> UserResponsePayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    user = payload.get("user")
    assert isinstance(user, dict)
    user_id = user.get("user_id")
    user_name = user.get("user_name")
    assert isinstance(user_id, str)
    assert isinstance(user_name, str)
    return {"user": {"user_id": user_id, "user_name": user_name}}


def _error_payload(response_text: str) -> ErrorResponsePayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    error = payload.get("error")
    message = payload.get("message")
    assert isinstance(error, str)
    assert isinstance(message, str)
    result: ErrorResponsePayload = {"error": error, "message": message}
    field_errors = payload.get("field_errors")
    if isinstance(field_errors, dict):
        typed_field_errors: FieldErrorsPayload = {}
        user_id_error = field_errors.get("user_id")
        if isinstance(user_id_error, str):
            typed_field_errors["user_id"] = user_id_error
        user_name_error = field_errors.get("user_name")
        if isinstance(user_name_error, str):
            typed_field_errors["user_name"] = user_name_error
        password_error = field_errors.get("password")
        if isinstance(password_error, str):
            typed_field_errors["password"] = password_error
        password_confirmation_error = field_errors.get("password_confirmation")
        if isinstance(password_confirmation_error, str):
            typed_field_errors["password_confirmation"] = password_confirmation_error
        current_password_error = field_errors.get("current_password")
        if isinstance(current_password_error, str):
            typed_field_errors["current_password"] = current_password_error
        new_password_error = field_errors.get("new_password")
        if isinstance(new_password_error, str):
            typed_field_errors["new_password"] = new_password_error
        new_password_confirmation_error = field_errors.get(
            "new_password_confirmation",
        )
        if isinstance(new_password_confirmation_error, str):
            typed_field_errors["new_password_confirmation"] = (
                new_password_confirmation_error
            )
        result["field_errors"] = typed_field_errors
    return result


def _assert_login_cookie_attributes(set_cookie: str) -> None:
    assert f"{LOGIN_SESSION_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    assert "Path=/" in set_cookie
    assert "Max-Age=34560000" in set_cookie


def _assert_expired_cookie(set_cookie: str) -> None:
    assert f"{LOGIN_SESSION_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()

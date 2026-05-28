from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.shared.user_messages import PASSWORD_FORMAT_MESSAGE
from backend.tests.integration.test_api_vertical_mvp import _make_config
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_register_sets_cookie_and_me_returns_current_user(tmp_path: Path) -> None:
    """観点：I-ACC-001、I-ACC-002。確認：登録成功でCookieと現在ユーザを返す。"""
    client = _make_client(tmp_path)

    response = client.post(
        "/api/auth/register",
        json={
            "user_id": "demo-user",
            "user_name": "デモユーザ",
            "password": "abc12",
            "password_confirmation": "abc12",
        },
    )
    me_response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "user": {"user_id": "demo-user", "user_name": "デモユーザ"}
    }
    assert client.cookies.get("d_concierge_session")
    assert me_response.status_code == 200
    assert me_response.json() == response.json()


def test_register_validation_and_duplicate_return_field_errors(
    tmp_path: Path,
) -> None:
    """観点：I-ACC-003。確認：登録入力不正と重複を項目別エラーで返す。"""
    client = _make_client(tmp_path)
    client.post(
        "/api/auth/register",
        json={
            "user_id": "demo-user",
            "user_name": "デモユーザ",
            "password": "abc12",
            "password_confirmation": "abc12",
        },
    )

    response = client.post(
        "/api/auth/register",
        json={
            "user_id": "demo-user",
            "user_name": "",
            "password": "abcd",
            "password_confirmation": "zzzzz",
        },
    )

    assert response.status_code == 400
    assert response.json()["field_errors"] == {
        "user_id": "このユーザIDは既に使用されています。",
        "user_name": "ユーザ名を入力してください。",
        "password": PASSWORD_FORMAT_MESSAGE,
        "password_confirmation": "同じパスワードを入力してください。",
    }


def test_login_success_and_failure_return_expected_contract(tmp_path: Path) -> None:
    """観点：I-ACC-004、I-ACC-005。確認：ログイン成功と失敗を設計どおり返す。"""
    client = _make_client(tmp_path)
    client.post(
        "/api/auth/register",
        json={
            "user_id": "demo-user",
            "user_name": "デモユーザ",
            "password": "abc12",
            "password_confirmation": "abc12",
        },
    )
    client.post("/api/auth/logout")

    failed = client.post(
        "/api/auth/login",
        json={"user_id": "demo-user", "password": "wrong1"},
    )
    succeeded = client.post(
        "/api/auth/login",
        json={"user_id": "demo-user", "password": "abc12"},
    )

    assert failed.status_code == 400
    assert failed.json()["field_errors"] == {
        "password": "パスワードが正しくありません。"
    }
    assert succeeded.status_code == 200
    assert succeeded.json()["user"] == {
        "user_id": "demo-user",
        "user_name": "デモユーザ",
    }


def test_protected_api_requires_login_and_logout_clears_session(
    tmp_path: Path,
) -> None:
    """観点：I-ACC-006、I-ACC-014。確認：保護APIは未ログインを拒否しログアウト後も拒否する。"""
    client = _make_client(tmp_path)

    unauthorized = client.get("/api/app-config")
    client.post(
        "/api/auth/register",
        json={
            "user_id": "demo-user",
            "user_name": "デモユーザ",
            "password": "abc12",
            "password_confirmation": "abc12",
        },
    )
    authorized = client.get("/api/app-config")
    logout = client.post("/api/auth/logout")
    after_logout = client.get("/api/app-config")

    assert unauthorized.status_code == 401
    assert unauthorized.json()["message"] == "ログインしてください。"
    assert authorized.status_code == 200
    assert logout.status_code == 204
    assert after_logout.status_code == 401


def test_account_name_password_and_delete_flow(tmp_path: Path) -> None:
    """観点：I-ACC-007、I-ACC-009、I-ACC-011。確認：変更と削除受付を行う。"""
    client = _make_client(tmp_path)
    client.post(
        "/api/auth/register",
        json={
            "user_id": "demo-user",
            "user_name": "デモユーザ",
            "password": "abc12",
            "password_confirmation": "abc12",
        },
    )

    name_response = client.patch("/api/account/name", json={"user_name": "新ユーザ"})
    password_response = client.patch(
        "/api/account/password",
        json={
            "current_password": "abc12",
            "new_password": "new12",
            "new_password_confirmation": "new12",
        },
    )
    delete_response = client.delete("/api/account")
    me_response = client.get("/api/auth/me")

    assert name_response.status_code == 200
    assert name_response.json()["user"] == {
        "user_id": "demo-user",
        "user_name": "新ユーザ",
    }
    assert password_response.status_code == 204
    assert delete_response.status_code == 202
    assert delete_response.json() == {"account_state": "deleting"}
    assert me_response.status_code == 401


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        config=_make_config(tmp_path),
        repository=InMemoryChatRepository(),
        run_dispatcher=None,
    )
    return TestClient(app)

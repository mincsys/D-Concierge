from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import pytest
from fastapi import Cookie, HTTPException, status
from httpx import ASGITransport, AsyncClient

from backend.tests.support.foundation import (
    LOGIN_SESSION_COOKIE_NAME,
    VALID_SESSION_TOKEN,
    create_foundation_config,
)


class AppConfigResponsePayload(TypedDict):
    welcome_message: str | None
    sub_welcome_message: str | None
    input_suggestions: tuple[str, ...]


class ErrorResponsePayload(TypedDict):
    error: str
    message: str


@dataclass(frozen=True, slots=True)
class AuthenticatedUserForTest:
    user_id: str
    user_name: str


@pytest.mark.asyncio
async def test_get_app_config_returns_only_public_ui_settings(tmp_path: Path) -> None:
    """
    観点：REST境界と設定読込がアプリ設定取得IFとして結合されること
    確認：有効なログインセッションCookie付きのGET /api/app-configだけが200となり、
    歓迎メッセージ、補足案内文、入力候補だけを返すこと
    """
    from backend.app.factory import create_app
    from backend.presentation.rest.dependencies import get_authenticated_user

    files = create_foundation_config(tmp_path)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    app.dependency_overrides[get_authenticated_user] = require_test_authenticated_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, VALID_SESSION_TOKEN)
        response = await client.get("/api/app-config")

    assert response.status_code == 200
    assert response.headers["x-trace-id"]
    payload = _app_config_payload(response.text)
    assert payload["welcome_message"] == "ようこそ"
    assert payload["sub_welcome_message"] == "必要な資料を指定してください"
    assert payload["input_suggestions"] == (
        "申請手順を確認したい",
        "参考資料の該当ページを知りたい",
    )
    response_text = response.text
    assert "database" not in response_text
    assert "postgresql" not in response_text
    assert "codex_docker" not in response_text
    assert "trace_log" not in response_text
    assert str(files.data_source_dir) not in response_text
    assert str(files.trace_log_dir) not in response_text


@pytest.mark.asyncio
async def test_get_app_config_treats_missing_ui_as_empty_public_payload(
    tmp_path: Path,
) -> None:
    """
    観点：UI設定不足時も開始画面を利用可能にすること
    確認：有効なログインセッションCookieがあり、ui設定が未定義のconfig.yamlでも
    GET /api/app-configは200を返し、公開payloadは空文字または空配列相当になること
    """
    from backend.app.factory import create_app
    from backend.presentation.rest.dependencies import get_authenticated_user

    files = create_foundation_config(tmp_path, include_ui=False)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    app.dependency_overrides[get_authenticated_user] = require_test_authenticated_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, VALID_SESSION_TOKEN)
        response = await client.get("/api/app-config")

    assert response.status_code == 200
    assert response.headers["x-trace-id"]
    payload = _app_config_payload(response.text)
    assert payload["welcome_message"] in (None, "")
    assert payload["sub_welcome_message"] in (None, "")
    assert payload["input_suggestions"] == ()


@pytest.mark.asyncio
async def test_get_app_config_rejects_missing_or_invalid_session_cookie(
    tmp_path: Path,
) -> None:
    """
    観点：アプリ設定取得IFが保護対象APIとして認証依存関係を通ること
    確認：ログインセッションCookieがない場合と不正なCookie値の場合は
    GET /api/app-configが401を返し、内部設定を公開しないこと
    """
    from backend.app.factory import create_app
    from backend.presentation.rest.dependencies import get_authenticated_user

    files = create_foundation_config(tmp_path)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)
    app.dependency_overrides[get_authenticated_user] = require_test_authenticated_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        missing_cookie_response = await client.get("/api/app-config")
        client.cookies.set(LOGIN_SESSION_COOKIE_NAME, "invalid-session-token")
        invalid_cookie_response = await client.get("/api/app-config")

    assert missing_cookie_response.status_code == 401
    assert invalid_cookie_response.status_code == 401
    assert missing_cookie_response.headers["x-trace-id"]
    assert invalid_cookie_response.headers["x-trace-id"]
    for response_text in (missing_cookie_response.text, invalid_cookie_response.text):
        payload = _error_payload(response_text)
        assert payload["error"] == "unauthorized"
        assert payload["message"] == "ログインしてください。"
        assert "detail" not in response_text
        assert "postgresql" not in response_text
        assert "codex_docker" not in response_text
        assert str(files.trace_log_dir) not in response_text


async def require_test_authenticated_user(
    session_token: str | None = Cookie(default=None, alias=LOGIN_SESSION_COOKIE_NAME),
) -> AuthenticatedUserForTest:
    if session_token != VALID_SESSION_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインしてください。",
        )
    return AuthenticatedUserForTest(user_id="user-001", user_name="テストユーザ")


def _app_config_payload(response_text: str) -> AppConfigResponsePayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    welcome_message = payload.get("welcome_message")
    sub_welcome_message = payload.get("sub_welcome_message")
    input_suggestions = payload.get("input_suggestions")
    assert isinstance(welcome_message, str) or welcome_message is None
    assert isinstance(sub_welcome_message, str) or sub_welcome_message is None
    assert isinstance(input_suggestions, list)
    assert all(isinstance(item, str) for item in input_suggestions)
    return {
        "welcome_message": welcome_message,
        "sub_welcome_message": sub_welcome_message,
        "input_suggestions": tuple(input_suggestions),
    }


def _error_payload(response_text: str) -> ErrorResponsePayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    error = payload.get("error")
    message = payload.get("message")
    assert isinstance(error, str)
    assert isinstance(message, str)
    return {"error": error, "message": message}

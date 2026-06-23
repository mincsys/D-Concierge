from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from backend.tests.support.foundation import create_foundation_config


class ErrorResponsePayload(TypedDict):
    error: str
    message: str


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_type_value", "expected_status", "expected_error"),
    (
        ("input", 400, "validation_error"),
        ("not_found", 404, "not_found"),
        ("conflict", 409, "conflict"),
        ("configuration", 500, "configuration_error"),
        ("forbidden", 403, "forbidden"),
        ("system", 500, "internal_error"),
    ),
)
async def test_app_error_is_converted_to_common_rest_error_payload(
    tmp_path: Path,
    error_type_value: str,
    expected_status: int,
    expected_error: str,
) -> None:
    """
    観点：AppErrorがREST共通エラー応答へ変換されること
    確認：各ErrorTypeがHTTPステータス、error/message payload、
    x-trace-idヘッダーへ変換され、detailを返さないこと
    """
    from backend.shared.errors.error_type import ErrorType
    from backend.shared.errors.errors import AppError

    app = _create_error_test_app(tmp_path)

    @app.get("/api/__test__/app-error")
    async def raise_app_error() -> None:
        raise AppError(
            error_type=ErrorType(error_type_value),
            trace=expected_status >= 500,
            diagnostic_message=f"{error_type_value} diagnostic",
        )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/__test__/app-error")

    assert response.status_code == expected_status
    assert response.headers["x-trace-id"]
    payload = _error_payload(response.text)
    assert payload["error"] == expected_error
    assert payload["message"]
    assert "detail" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    (
        (401, "unauthorized"),
        (403, "forbidden"),
        (404, "not_found"),
        (409, "conflict"),
        (422, "validation_error"),
        (500, "internal_error"),
    ),
)
async def test_http_exception_is_converted_to_common_rest_error_payload(
    tmp_path: Path,
    status_code: int,
    expected_error: str,
) -> None:
    """
    観点：HTTPExceptionがFastAPI標準detailではなくREST共通エラー応答へ変換されること
    確認：代表HTTPステータスがerror/message payloadとx-trace-idヘッダーを返し、
    detailを返さないこと
    """
    app = _create_error_test_app(tmp_path)

    @app.get("/api/__test__/http-error")
    async def raise_http_error() -> None:
        raise HTTPException(status_code=status_code, detail="HTTPエラーです。")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/__test__/http-error")

    assert response.status_code == status_code
    assert response.headers["x-trace-id"]
    payload = _error_payload(response.text)
    assert payload["error"] == expected_error
    assert payload["message"] == "HTTPエラーです。"
    assert "detail" not in response.text


@pytest.mark.asyncio
async def test_http_exception_non_string_detail_uses_default_message(
    tmp_path: Path,
) -> None:
    """
    観点：HTTPExceptionのdetailが文字列以外でも内部構造を公開しないこと
    確認：非文字列detailはREST共通エラー応答の既定メッセージに変換されること
    """
    app = _create_error_test_app(tmp_path)

    @app.get("/api/__test__/http-error-non-string")
    async def raise_http_error() -> None:
        raise HTTPException(status_code=418, detail={"reason": "hidden"})

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/__test__/http-error-non-string")

    payload = _error_payload(response.text)
    assert response.status_code == 418
    assert payload["error"] == "validation_error"
    assert payload["message"] == "入力内容を確認してください。"
    assert "hidden" not in response.text


@pytest.mark.asyncio
async def test_request_validation_error_uses_common_rest_error_payload(
    tmp_path: Path,
) -> None:
    """
    観点：FastAPIの入力検証エラーがREST共通エラー応答へ変換されること
    確認：型不一致のpath parameterは400、validation_error、
    利用者向けmessageを返し、detailを返さないこと
    """
    app = _create_error_test_app(tmp_path)

    @app.get("/api/__test__/items/{item_id}")
    async def validate_path_parameter(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/__test__/items/not-an-int")

    assert response.status_code == 400
    assert response.headers["x-trace-id"]
    payload = _error_payload(response.text)
    assert payload["error"] == "validation_error"
    assert payload["message"] == "入力内容を確認してください。"
    assert "detail" not in response.text


def _create_error_test_app(tmp_path: Path) -> FastAPI:
    from backend.app.factory import create_app

    files = create_foundation_config(tmp_path)
    return create_app(config_path=files.config_path, base_dir=tmp_path)


def _error_payload(response_text: str) -> ErrorResponsePayload:
    payload = json.loads(response_text)
    assert isinstance(payload, dict)
    error = payload.get("error")
    message = payload.get("message")
    assert isinstance(error, str)
    assert isinstance(message, str)
    return {"error": error, "message": message}

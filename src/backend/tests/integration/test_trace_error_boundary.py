from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from backend.shared.user_messages import NOT_FOUND, SYSTEM_ERROR
from backend.tests.support.foundation import create_foundation_config


class TraceLogYamlPayload(TypedDict):
    occurred_at: datetime
    trace_id: str
    event_name: str
    stage: str
    user_id: str | None
    chat_id: str | None
    run_id: str | None
    reference_id: str | None
    artifact_id: str | None
    error_type: str
    message: str
    exception_type: str
    stacktrace: str
    http_method: str
    path: str
    status_code: int


class ErrorResponsePayload(TypedDict):
    error: str
    message: str


@pytest.mark.asyncio
async def test_unexpected_api_error_returns_trace_id_and_writes_trace_log(
    tmp_path: Path,
) -> None:
    """
    観点：REST共通例外ハンドラとtrace_idとトレースログが結合されること
    確認：予期しない例外は500応答にtrace_idを含め、発生日時、例外型、
    stacktrace、HTTP情報、関連ID欄を持つYAMLログを1異常1ファイルで保存すること
    """
    from backend.app.factory import create_app

    files = create_foundation_config(tmp_path)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    @app.get("/api/__test__/unexpected-error")
    async def raise_unexpected_error() -> None:
        raise RuntimeError("integration test failure")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/__test__/unexpected-error")

    assert response.status_code == 500
    assert response.headers["x-trace-id"]
    error_payload = _error_payload(response.text)
    assert error_payload["error"] == "internal_error"
    assert error_payload["message"] == SYSTEM_ERROR
    assert "detail" not in response.text
    assert "trace_id" not in response.text
    log_files = tuple(
        path
        for path in files.trace_log_dir.rglob("*.yaml")
        if "api_failed" in path.name
    )
    assert len(log_files) == 1

    trace_log_keys = _yaml_mapping_keys(log_files[0])
    for required_key in (
        "occurred_at",
        "trace_id",
        "event_name",
        "stage",
        "user_id",
        "chat_id",
        "run_id",
        "reference_id",
        "artifact_id",
        "error_type",
        "message",
        "exception_type",
        "stacktrace",
        "http_method",
        "path",
        "status_code",
    ):
        assert required_key in trace_log_keys

    trace_log = _trace_log_payload(log_files[0])
    assert trace_log["trace_id"] == response.headers["x-trace-id"]
    assert trace_log["event_name"] == "api_failed"
    assert trace_log["stage"] == "presentation.rest"
    assert trace_log["error_type"] == "system"
    assert "integration test failure" in trace_log["message"]
    assert trace_log["exception_type"] == "RuntimeError"
    assert "raise_unexpected_error" in trace_log["stacktrace"]
    assert trace_log["http_method"] == "GET"
    assert trace_log["path"] == "/api/__test__/unexpected-error"
    assert trace_log["status_code"] == 500
    assert trace_log["user_id"] in (None, "")
    assert trace_log["chat_id"] in (None, "")
    assert trace_log["run_id"] in (None, "")
    assert trace_log["reference_id"] in (None, "")
    assert trace_log["artifact_id"] in (None, "")


@pytest.mark.asyncio
async def test_http_exception_uses_common_error_payload_without_detail(
    tmp_path: Path,
) -> None:
    """
    観点：FastAPI標準HTTPExceptionがREST共通エラー応答へ変換されること
    確認：HTTPExceptionのdetailオブジェクトを公開せず、API IFのerror/message形式と
    trace_idヘッダーだけを返すこと
    """
    from backend.app.factory import create_app

    files = create_foundation_config(tmp_path)
    app = create_app(config_path=files.config_path, base_dir=tmp_path)

    @app.get("/api/__test__/missing")
    async def raise_not_found() -> None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"internal_path": "/secret/config.yaml"},
        )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/__test__/missing")

    assert response.status_code == 404
    assert response.headers["x-trace-id"]
    payload = _error_payload(response.text)
    assert payload["error"] == "not_found"
    assert payload["message"] == NOT_FOUND
    assert "detail" not in response.text
    assert "internal_path" not in response.text
    assert "trace_id" not in response.text


def test_create_app_prunes_expired_trace_log_date_directories(tmp_path: Path) -> None:
    """
    観点：アプリ起動時にtrace_log.retention_daysが保持期間削除へ反映されること
    確認：保持期間を過ぎた日付ディレクトリだけが削除され、保持対象ディレクトリは残ること
    """
    from backend.app.factory import create_app

    files = create_foundation_config(tmp_path, trace_retention_days=1)
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    expired_dir = files.trace_log_dir / (today - timedelta(days=2)).isoformat()
    kept_dir = files.trace_log_dir / today.isoformat()
    expired_dir.mkdir(parents=True)
    kept_dir.mkdir(parents=True)
    (expired_dir / "old.yaml").write_text("old: true\n", encoding="utf-8")
    (kept_dir / "new.yaml").write_text("new: true\n", encoding="utf-8")

    create_app(config_path=files.config_path, base_dir=tmp_path)

    assert not expired_dir.exists()
    assert kept_dir.exists()
    assert (kept_dir / "new.yaml").exists()


def test_create_app_writes_trace_log_when_config_loading_fails(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込失敗がアプリ生成失敗としてトレースログへ記録されること
    確認：trace_log.dirが有効な場合、設定不備でcreate_appが失敗してもapp_startup_failedのYAMLが保存されること
    """
    from backend.app.factory import create_app
    from backend.shared.errors.errors import AppError

    files = create_foundation_config(tmp_path)
    broken_text = files.config_path.read_text(encoding="utf-8").replace(
        '  url: "postgresql+psycopg://user:password@localhost:5432/d_concierge"\n',
        "",
    )
    files.config_path.write_text(broken_text, encoding="utf-8")

    with pytest.raises(AppError):
        create_app(config_path=files.config_path, base_dir=tmp_path)

    log_files = tuple(files.trace_log_dir.rglob("*.yaml"))
    assert len(log_files) == 1
    trace_log = _trace_log_payload(log_files[0])
    assert trace_log["event_name"] == "app_startup_failed"
    assert trace_log["stage"] == "app.factory"
    assert trace_log["error_type"] == "configuration"
    assert "database.url" in trace_log["message"]
    assert trace_log["path"] == str(files.config_path)


def test_create_app_writes_startup_trace_log_to_fallback_when_trace_dir_is_invalid(
    tmp_path: Path,
) -> None:
    """
    観点：trace_log.dir自体が不正な設定読込失敗でも診断情報を残すこと
    確認：trace_log.dirが既存ファイルを指す場合、起動失敗用fallbackディレクトリへ設定不備ログが保存されること
    """
    from backend.app.factory import create_app
    from backend.shared.errors.errors import AppError

    files = create_foundation_config(tmp_path)
    trace_log_file = tmp_path / "trace-log-as-file"
    trace_log_file.write_text("not directory\n", encoding="utf-8")
    config_text = files.config_path.read_text(encoding="utf-8")
    files.config_path.write_text(
        config_text.replace(files.trace_log_dir.as_posix(), trace_log_file.as_posix()),
        encoding="utf-8",
    )

    with pytest.raises(AppError):
        create_app(config_path=files.config_path, base_dir=tmp_path)

    fallback_log_files = tuple((tmp_path / "trace_log_startup_errors").rglob("*.yaml"))
    assert len(fallback_log_files) == 1
    trace_log = _trace_log_payload(fallback_log_files[0])
    assert trace_log["event_name"] == "app_startup_failed"
    assert "trace_log.dir" in trace_log["message"]


def _yaml_mapping_keys(path: Path) -> tuple[str, ...]:
    loaded_yaml = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert hasattr(loaded_yaml, "keys")
    return tuple(str(key) for key in loaded_yaml.keys())


def _trace_log_payload(path: Path) -> TraceLogYamlPayload:
    loaded_yaml = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded_yaml, dict)
    occurred_at_text = loaded_yaml.get("occurred_at")
    trace_id = loaded_yaml.get("trace_id")
    event_name = loaded_yaml.get("event_name")
    stage = loaded_yaml.get("stage")
    error_type = loaded_yaml.get("error_type")
    message = loaded_yaml.get("message")
    exception_type = loaded_yaml.get("exception_type")
    stacktrace = loaded_yaml.get("stacktrace")
    http_method = loaded_yaml.get("http_method")
    request_path = loaded_yaml.get("path")
    status_code = loaded_yaml.get("status_code")
    assert isinstance(occurred_at_text, str)
    assert isinstance(trace_id, str)
    assert isinstance(event_name, str)
    assert isinstance(stage, str)
    assert isinstance(error_type, str)
    assert isinstance(message, str)
    assert isinstance(exception_type, str)
    assert isinstance(stacktrace, str)
    assert isinstance(http_method, str)
    assert isinstance(request_path, str)
    assert isinstance(status_code, int)
    return {
        "occurred_at": datetime.fromisoformat(occurred_at_text),
        "trace_id": trace_id,
        "event_name": event_name,
        "stage": stage,
        "user_id": _optional_string(loaded_yaml.get("user_id")),
        "chat_id": _optional_string(loaded_yaml.get("chat_id")),
        "run_id": _optional_string(loaded_yaml.get("run_id")),
        "reference_id": _optional_string(loaded_yaml.get("reference_id")),
        "artifact_id": _optional_string(loaded_yaml.get("artifact_id")),
        "error_type": error_type,
        "message": message,
        "exception_type": exception_type,
        "stacktrace": stacktrace,
        "http_method": http_method,
        "path": request_path,
        "status_code": status_code,
    }


def _error_payload(response_text: str) -> ErrorResponsePayload:
    loaded_json = json.loads(response_text)
    assert isinstance(loaded_json, dict)
    error = loaded_json.get("error")
    message = loaded_json.get("message")
    assert isinstance(error, str)
    assert isinstance(message, str)
    return {"error": error, "message": message}


def _optional_string(value: str | None) -> str | None:
    assert isinstance(value, str) or value is None
    return value

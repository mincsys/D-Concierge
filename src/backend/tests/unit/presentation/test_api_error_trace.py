from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.application.ports.database.dto import HistoryItem
from backend.infrastructure.config.models import (
    AppConfig,
    AppRuntimeConfig,
    CodexDockerConfig,
    DatabaseConfig,
    GeneratorConfig,
    ServerConfig,
    TraceLogConfig,
    UiConfig,
    ValidatorConfig,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_repository_system_error_returns_500(tmp_path: Path) -> None:
    """観点：エラー変換。確認：RepositoryのSYSTEM例外をHTTP 500にする。"""
    app = create_app(
        config=_make_config(tmp_path),
        repository=BrokenHistoryRepository(),
        run_dispatcher=None,
    )
    client = TestClient(app)
    _register_test_user(client)

    response = client.get("/api/chat-histories")

    assert response.status_code == 500


def test_unexpected_api_error_writes_system_trace_log(tmp_path: Path) -> None:
    """観点：トレースログ。確認：想定外例外をSYSTEM分類のAPI失敗ログへ保存する。"""
    app = create_app(
        config=_make_config(tmp_path),
        repository=UnexpectedHistoryRepository(),
        run_dispatcher=None,
    )
    client = TestClient(app, raise_server_exceptions=False)
    _register_test_user(client)

    response = client.get("/api/chat-histories")

    assert response.status_code == 500
    records = _trace_records(tmp_path)
    assert any(
        record["event_name"] == "api_failed"
        and record["stage"] == "chat_histories"
        and record["error_type"] == "system"
        and record["exception_type"] == "RuntimeError"
        and "stacktrace" in record
        for record in records
    )


def test_create_app_writes_trace_log_with_app_timezone_path(tmp_path: Path) -> None:
    """観点：トレースログ。確認：アプリ共通タイムゾーンの日時でログパスを作る。"""
    app = create_app(
        config=_make_config(tmp_path),
        repository=UnexpectedHistoryRepository(),
        run_dispatcher=None,
        clock=FixedClock(datetime(2026, 5, 10, 15, 0, tzinfo=UTC)),
    )
    client = TestClient(app, raise_server_exceptions=False)
    _register_test_user(client)

    response = client.get("/api/chat-histories")

    assert response.status_code == 500
    log_path = tmp_path / "logs/trace/2026-05-11/00-00-00_000000_api_failed.yaml"
    payload = yaml.safe_load(log_path.read_text(encoding="utf-8"))
    assert payload["occurred_at"] == "2026-05-11T00:00:00+09:00"
    assert payload["event_name"] == "api_failed"


class BrokenHistoryRepository(InMemoryChatRepository):
    """履歴一覧でシステム例外を返すテスト用Repository。"""

    def list_histories(self, user_id: str = "") -> tuple[HistoryItem, ...]:
        """システム例外を発生させる。"""
        _ = user_id
        raise AppError(
            ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="DB接続に失敗しました。",
        )


class UnexpectedHistoryRepository(InMemoryChatRepository):
    """履歴一覧で想定外例外を返すテスト用Repository。"""

    def list_histories(self, user_id: str = "") -> tuple[HistoryItem, ...]:
        """想定外例外を発生させる。"""
        _ = user_id
        raise RuntimeError("unexpected failure")


class FixedClock:
    """テスト用に固定時刻を返す時計。"""

    def __init__(self, now_value: datetime) -> None:
        self._now_value = now_value

    def now(self) -> datetime:
        """UTC基準の現在時刻を返す。"""
        return self.now_utc()

    def now_utc(self) -> datetime:
        """UTC基準の現在時刻を返す。"""
        return self._now_value.astimezone(UTC)

    def now_app_timezone(self) -> datetime:
        """アプリタイムゾーン基準の現在時刻を返す。"""
        return self.now_utc().astimezone(ZoneInfo("Asia/Tokyo"))


def _register_test_user(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "user_id": "demo-user",
            "user_name": "デモユーザ",
            "password": "abc12",
            "password_confirmation": "abc12",
        },
    )
    assert response.status_code == 200


def _make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        app=AppRuntimeConfig(timezone=ZoneInfo("Asia/Tokyo")),
        ui=UiConfig(
            welcome_message="ようこそ",
            input_suggestions=("要約してください",),
        ),
        datasource_dir=tmp_path / "readonly",
        generator=GeneratorConfig(
            max_retries=2,
            home=tmp_path / "codex/.codex",
            workdir=tmp_path / "codex/sessions",
            output_schema=tmp_path
            / "codex/output_json_schema/pdf-reference-schema.json",
            saved_artifacts_dir=tmp_path / "codex/saved_artifacts",
        ),
        validator=ValidatorConfig(
            max_retries=3,
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "codex/output_json_schema/validator_schema.json",
        ),
        codex_docker=CodexDockerConfig(
            image="codex-python-runner:latest",
            workspace_dir="/workspace",
            codex_home_dir="/home/codex/.codex",
            codex_api_key="",
        ),
        database=DatabaseConfig(
            url="postgresql+psycopg://user:password@127.0.0.1:5432/db"
        ),
        server=ServerConfig(timeout_seconds=300),
        trace_log=TraceLogConfig(
            dir=tmp_path / "logs/trace",
            retention_days=90,
            max_files_per_day=1000,
        ),
    )


def _trace_records(tmp_path: Path) -> list[dict[str, str]]:
    log_files = sorted((tmp_path / "logs/trace").glob("*/*.yaml"))
    records: list[dict[str, str]] = []
    for log_file in log_files:
        loaded = yaml.safe_load(log_file.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)
        records.append({str(key): str(value) for key, value in loaded.items()})
    return records

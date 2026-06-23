from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class AppSectionSettings:
    """アプリケーション共通設定。"""

    timezone: ZoneInfo


@dataclass(frozen=True, slots=True)
class UiSectionSettings:
    """画面へ公開できるUI設定。"""

    welcome_message: str | None = None
    sub_welcome_message: str | None = None
    input_suggestions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataSourceSectionSettings:
    """共有データソース設定。"""

    dir: Path


@dataclass(frozen=True, slots=True)
class CodexWorkerSectionSettings:
    """用途別Codex実行設定。"""

    max_retries: int
    home: Path
    workdir: Path
    output_schema: Path
    saved_artifacts_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class CodexDockerSectionSettings:
    """Codex実行コンテナ設定。"""

    image: str
    workspace_dir: str
    codex_home_dir: str
    codex_api_key: str


@dataclass(frozen=True, slots=True)
class DatabaseSectionSettings:
    """DB接続設定。"""

    url: str


@dataclass(frozen=True, slots=True)
class ServerSectionSettings:
    """サーバ実行制約設定。"""

    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class TraceLogSectionSettings:
    """異常系トレースログ設定。"""

    dir: Path
    retention_days: int
    max_files_per_day: int


@dataclass(frozen=True, slots=True)
class StartupTraceLogSettings:
    """アプリ生成失敗時にも使える最小トレースログ設定。"""

    dir: Path
    timezone: ZoneInfo
    retention_days: int
    max_files_per_day: int


@dataclass(frozen=True, slots=True)
class AppSettings:
    """config.yaml全体を型付けした設定。"""

    app: AppSectionSettings
    ui: UiSectionSettings
    data_source: DataSourceSectionSettings
    generator: CodexWorkerSectionSettings
    validator: CodexWorkerSectionSettings
    codex_docker: CodexDockerSectionSettings
    database: DatabaseSectionSettings
    server: ServerSectionSettings
    trace_log: TraceLogSectionSettings

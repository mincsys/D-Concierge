from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UiConfig:
    """画面へ公開するUI設定。"""

    welcome_message: str | None
    input_suggestions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CodexConfig:
    """codex execのホーム、作業領域、出力契約、成果物保存先設定。"""

    home: Path
    workdir: Path
    output_schema: Path
    saved_artifacts_dir: Path


@dataclass(frozen=True, slots=True)
class ValidatorConfig:
    """検証処理設定。"""

    max_retries: int
    codex: CodexConfig


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """DB接続設定。"""

    url: str


@dataclass(frozen=True, slots=True)
class ServerConfig:
    """サーバ実行制約設定。"""

    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class TraceLogConfig:
    """トレースログ保存先と保持設定。"""

    dir: Path
    retention_days: int
    max_files_per_day: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    """D-Conciergeバックエンドの型付き設定。"""

    ui: UiConfig
    datasource_dir: Path
    codex: CodexConfig
    validator: ValidatorConfig
    database: DatabaseConfig
    server: ServerConfig
    trace_log: TraceLogConfig

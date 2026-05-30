from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class AppRuntimeConfig:
    """アプリケーション共通の実行時設定。"""

    timezone: ZoneInfo


@dataclass(frozen=True, slots=True)
class UiConfig:
    """画面へ公開するUI設定。"""

    welcome_message: str | None
    input_suggestions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    """生成用Codexの再生成上限、ホーム、作業領域、出力契約、成果物保存先設定。"""

    max_retries: int
    home: Path
    workdir: Path
    output_schema: Path
    saved_artifacts_dir: Path


@dataclass(frozen=True, slots=True)
class ValidatorConfig:
    """検証用Codexの再出力上限、ホーム、作業領域、出力契約設定。"""

    max_retries: int
    home: Path
    workdir: Path
    output_schema: Path


@dataclass(frozen=True, slots=True)
class CodexDockerConfig:
    """Codex実行コンテナの起動設定。"""

    image: str
    workspace_dir: str
    codex_home_dir: str
    codex_api_key: str


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

    app: AppRuntimeConfig
    ui: UiConfig
    data_source_dir: Path
    generator: GeneratorConfig
    validator: ValidatorConfig
    codex_docker: CodexDockerConfig
    database: DatabaseConfig
    server: ServerConfig
    trace_log: TraceLogConfig

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pytest import MonkeyPatch

from backend.infrastructure.config.loader import ConfigLoader
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

VALID_CONFIG = """
app:
  timezone: "Asia/Tokyo"
ui:
  welcome_message: "ようこそ"
  input_suggestions:
    - "要約してください"
datasource:
  dir: "data"
codex:
  home: "codex/.codex"
  workdir: "codex/sessions"
  output_schema: "codex/output_json_schema/pdf-reference-schema.json"
  saved_artifacts_dir: "codex/saved_artifacts"
validator:
  max_retries: 2
  codex:
    home: "codex/.codex_validator"
    workdir: "codex/sessions_validator"
    output_schema: "codex/output_json_schema/validator_schema.json"
database:
  url: "postgresql+psycopg://user:password@127.0.0.1:5432/db"
server:
  timeout_seconds: 300
trace_log:
  dir: "logs/trace"
  retention_days: 90
  max_files_per_day: 1000
"""


def test_config_loader_returns_typed_public_ui_settings(tmp_path: Path) -> None:
    """観点：設定読込。確認：YAML設定を型付き設定へ変換し、画面公開項目を取得できる。"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(VALID_CONFIG, encoding="utf-8")

    config = ConfigLoader.load(config_path, base_dir=tmp_path)

    assert config.ui.welcome_message == "ようこそ"
    assert config.ui.input_suggestions == ("要約してください",)
    assert config.app.timezone == ZoneInfo("Asia/Tokyo")
    assert config.app.timezone.key == "Asia/Tokyo"
    assert config.database.url == "postgresql+psycopg://user:password@127.0.0.1:5432/db"
    assert config.server.timeout_seconds == 300
    assert config.datasource_dir == tmp_path / "data"
    assert config.trace_log.retention_days == 90
    assert config.trace_log.max_files_per_day == 1000


def test_config_loader_resolves_relative_paths_from_relative_config_path(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """観点：設定読込。

    確認：相対パスで設定ファイルを指定しても、各ファイルシステム設定を絶対パスへ解決する。
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(VALID_CONFIG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = ConfigLoader.load(Path("config.yaml"))

    assert config.datasource_dir == tmp_path / "data"
    assert config.codex.home == tmp_path / "codex/.codex"
    assert config.codex.workdir == tmp_path / "codex/sessions"
    assert config.codex.output_schema == (
        tmp_path / "codex/output_json_schema/pdf-reference-schema.json"
    )
    assert config.validator.codex.home == tmp_path / "codex/.codex_validator"
    assert config.validator.codex.workdir == tmp_path / "codex/sessions_validator"
    assert config.trace_log.dir == tmp_path / "logs/trace"


def test_config_loader_rejects_invalid_timeout(tmp_path: Path) -> None:
    """観点：設定不備。確認：タイムアウトが正の整数でない場合は設定不備にする。"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        VALID_CONFIG.replace("timeout_seconds: 300", "timeout_seconds: 0"),
        encoding="utf-8",
    )

    with pytest.raises(AppError) as error_info:
        ConfigLoader.load(config_path, base_dir=tmp_path)

    assert error_info.value.error_type is ErrorType.CONFIGURATION


def test_config_loader_uses_absolute_paths_without_base_dir_join(
    tmp_path: Path,
) -> None:
    """観点：設定読込。

    確認：絶対パスで指定されたディレクトリやスキーマをそのまま設定へ反映する。
    """
    config_path = tmp_path / "config.yaml"
    absolute_config = (
        VALID_CONFIG.replace(
            'dir: "data"',
            f'dir: "{(tmp_path / "readonly").as_posix()}"',
        )
        .replace(
            'home: "codex/.codex"',
            f'home: "{(tmp_path / "home").as_posix()}"',
            1,
        )
        .replace(
            'workdir: "codex/sessions"',
            f'workdir: "{(tmp_path / "sessions").as_posix()}"',
            1,
        )
        .replace(
            'dir: "logs/trace"',
            f'dir: "{(tmp_path / "logs" / "trace").as_posix()}"',
        )
    )
    config_path.write_text(absolute_config, encoding="utf-8")

    config = ConfigLoader.load(config_path, base_dir=tmp_path / "base")

    assert config.datasource_dir == tmp_path / "readonly"
    assert config.codex.home == tmp_path / "home"
    assert config.codex.workdir == tmp_path / "sessions"
    assert config.trace_log.dir == tmp_path / "logs" / "trace"


@pytest.mark.parametrize(
    ("config_text", "message_part"),
    [
        ("[]", "ルート形式"),
        (VALID_CONFIG.replace("max_retries: 2", "max_retries: -1"), "検証再試行"),
        (
            VALID_CONFIG.replace(
                'url: "postgresql+psycopg://user:password@127.0.0.1:5432/db"',
                'url: ""',
            ),
            "database.url",
        ),
        (
            VALID_CONFIG.replace("timeout_seconds: 300", 'timeout_seconds: "300"'),
            "server.timeout_seconds",
        ),
        (
            VALID_CONFIG.replace('timezone: "Asia/Tokyo"', 'timezone: ""'),
            "app.timezone",
        ),
        (
            VALID_CONFIG.replace('timezone: "Asia/Tokyo"', "timezone: 1"),
            "app.timezone",
        ),
        (
            VALID_CONFIG.replace('timezone: "Asia/Tokyo"', 'timezone: "Invalid/Zone"'),
            "app.timezone",
        ),
        (
            VALID_CONFIG.replace('  timezone: "Asia/Tokyo"\n', ""),
            "app.timezone",
        ),
        (
            VALID_CONFIG.replace("retention_days: 90", "retention_days: 0"),
            "trace_log.retention_days",
        ),
        (
            VALID_CONFIG.replace("  retention_days: 90\n", ""),
            "trace_log.retention_days",
        ),
        (
            VALID_CONFIG.replace("retention_days: 90", "retention_days: true"),
            "trace_log.retention_days",
        ),
        (
            VALID_CONFIG.replace("retention_days: 90", 'retention_days: "90"'),
            "trace_log.retention_days",
        ),
        (
            VALID_CONFIG.replace("max_files_per_day: 1000", "max_files_per_day: 0"),
            "trace_log.max_files_per_day",
        ),
        (
            VALID_CONFIG.replace("max_files_per_day: 1000", "max_files_per_day: -1"),
            "trace_log.max_files_per_day",
        ),
        (
            VALID_CONFIG.replace("  max_files_per_day: 1000\n", ""),
            "trace_log.max_files_per_day",
        ),
        (
            VALID_CONFIG.replace("max_files_per_day: 1000", "max_files_per_day: true"),
            "trace_log.max_files_per_day",
        ),
        (
            VALID_CONFIG.replace(
                "max_files_per_day: 1000", 'max_files_per_day: "1000"'
            ),
            "trace_log.max_files_per_day",
        ),
        (
            VALID_CONFIG.replace('welcome_message: "ようこそ"', "welcome_message: 1"),
            "ui.welcome_message",
        ),
        (
            VALID_CONFIG.replace('- "要約してください"', "    value: 1"),
            "ui.input_suggestions",
        ),
        (
            VALID_CONFIG.replace('- "要約してください"', "    - 1"),
            "ui.input_suggestions",
        ),
    ],
)
def test_config_loader_rejects_invalid_yaml_values(
    tmp_path: Path,
    config_text: str,
    message_part: str,
) -> None:
    """観点：設定不備。

    確認：型、範囲、必須項目が契約外の場合は設定不備として扱う。
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(AppError) as error_info:
        ConfigLoader.load(config_path, base_dir=tmp_path)

    assert error_info.value.error_type is ErrorType.CONFIGURATION
    assert error_info.value.trace is True
    assert message_part in error_info.value.diagnostic_message


def test_config_loader_uses_empty_optional_ui_defaults(tmp_path: Path) -> None:
    """観点：任意設定。

    確認：UI任意設定が未指定の場合はNoneと空リスト相当で型付き設定を返す。
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        VALID_CONFIG.replace(
            """ui:
  welcome_message: "ようこそ"
  input_suggestions:
    - "要約してください"
""",
            "",
        ),
        encoding="utf-8",
    )

    config = ConfigLoader.load(config_path, base_dir=tmp_path)

    assert config.ui.welcome_message is None
    assert config.ui.input_suggestions == ()


def test_config_loader_accepts_null_optional_ui_values(tmp_path: Path) -> None:
    """観点：任意設定。

    確認：UI任意設定がnullの場合はNoneと空リスト相当で型付き設定を返す。
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        VALID_CONFIG.replace(
            'welcome_message: "ようこそ"', "welcome_message: null"
        ).replace(
            """input_suggestions:
    - "要約してください"
""",
            "input_suggestions: null\n",
        ),
        encoding="utf-8",
    )

    config = ConfigLoader.load(config_path, base_dir=tmp_path)

    assert config.ui.welcome_message is None
    assert config.ui.input_suggestions == ()


def test_config_loader_rejects_missing_file(tmp_path: Path) -> None:
    """観点：設定不備。確認：設定ファイルが読めない場合は設定不備として扱う。"""
    with pytest.raises(AppError) as error_info:
        ConfigLoader.load(tmp_path / "missing.yaml", base_dir=tmp_path)

    assert error_info.value.error_type is ErrorType.CONFIGURATION

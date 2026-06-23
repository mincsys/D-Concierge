from __future__ import annotations

from pathlib import Path

import pytest

from backend.tests.support.foundation import (
    FoundationConfigFiles,
    create_foundation_config,
)


def test_load_valid_config_returns_typed_settings(tmp_path: Path) -> None:
    """
    観点：設定読込IFがconfig.yamlを型付き設定へ変換すること
    確認：必須項目、空文字のCodex API Key、UI設定、正規化済みPathを
    生dictではない属性として参照できること
    """
    from backend.infrastructure.config.loader import ConfigLoader

    files = create_foundation_config(tmp_path)

    settings = ConfigLoader().load(files.config_path)

    assert not isinstance(settings, dict)
    assert str(settings.app.timezone) == "Asia/Tokyo"
    assert settings.ui.welcome_message == "ようこそ"
    assert settings.ui.sub_welcome_message == "必要な資料を指定してください"
    assert tuple(settings.ui.input_suggestions) == (
        "申請手順を確認したい",
        "参考資料の該当ページを知りたい",
    )
    assert settings.codex_docker.codex_api_key == ""
    assert settings.data_source.dir == files.data_source_dir.resolve()
    assert settings.generator.output_schema == files.generator_output_schema.resolve()
    assert settings.server.timeout_seconds == 120
    assert settings.trace_log.retention_days == 90


def test_load_missing_required_database_url_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込IFが必須項目欠落を起動前に検知すること
    確認：database.urlが欠落した場合はErrorType.CONFIGURATIONかつtrace=TrueのAppErrorになり、診断文に項目名が含まれること
    """
    from backend.infrastructure.config.loader import ConfigLoader
    from backend.shared.errors.error_type import ErrorType
    from backend.shared.errors.errors import AppError

    files = create_foundation_config(tmp_path)
    broken_text = files.config_path.read_text(encoding="utf-8").replace(
        '  url: "postgresql+psycopg://user:password@localhost:5432/d_concierge"\n',
        "",
    )
    files.config_path.write_text(broken_text, encoding="utf-8")

    with pytest.raises(AppError) as raised:
        ConfigLoader().load(files.config_path)

    assert raised.value.error_type is ErrorType.CONFIGURATION
    assert raised.value.trace is True
    assert "database.url" in raised.value.diagnostic_message


@pytest.mark.parametrize(
    ("line_to_remove", "expected_field"),
    (
        ('  timezone: "Asia/Tokyo"\n', "app.timezone"),
        (f'  dir: "{Path("data_source").as_posix()}"\n', "data_source.dir"),
    ),
)
def test_load_missing_required_foundation_settings_raises_configuration_error(
    tmp_path: Path,
    line_to_remove: str,
    expected_field: str,
) -> None:
    """
    観点：設定読込IFが基盤設定の必須項目欠落を検知すること
    確認：app、data_sourceなどの必須項目が欠落した場合はErrorType.CONFIGURATIONとなり、診断文に対象項目名が含まれること
    """
    files = create_foundation_config(tmp_path)
    if expected_field == "data_source.dir":
        line_to_remove = f'  dir: "{files.data_source_dir.as_posix()}"\n'

    _remove_config_line(files.config_path, line_to_remove)

    _assert_configuration_error(files.config_path, (expected_field,))


@pytest.mark.parametrize(
    "expected_field",
    (
        "generator.max_retries",
        "generator.home",
        "generator.workdir",
        "generator.output_schema",
        "generator.saved_artifacts_dir",
        "validator.max_retries",
        "validator.home",
        "validator.workdir",
        "validator.output_schema",
        "codex_docker.image",
        "codex_docker.workspace_dir",
        "codex_docker.codex_home_dir",
        "codex_docker.codex_api_key",
        "server.timeout_seconds",
        "trace_log.dir",
        "trace_log.retention_days",
        "trace_log.max_files_per_day",
    ),
)
def test_load_missing_required_nested_settings_raises_configuration_error(
    tmp_path: Path,
    expected_field: str,
) -> None:
    """
    観点：設定読込IFがCodex、サーバ、トレースログの必須項目欠落を検知すること
    確認：generator、validator、codex_docker、server、trace_logの必須項目が欠落した場合は設定不備として拒否され、診断文に対象項目名が含まれること
    """
    files = create_foundation_config(tmp_path)

    _remove_required_nested_setting(files, expected_field)

    _assert_configuration_error(files.config_path, (expected_field,))


def test_load_invalid_positive_number_settings_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込IFが数値範囲を検証すること
    確認：timeout_seconds、trace_log.retention_days、trace_log.max_files_per_dayの正数制約違反が設定不備として拒否されること
    """
    from backend.infrastructure.config.loader import ConfigLoader
    from backend.shared.errors.error_type import ErrorType
    from backend.shared.errors.errors import AppError

    files = create_foundation_config(
        tmp_path,
        timeout_seconds=0,
        trace_retention_days=0,
        trace_max_files_per_day=0,
    )

    with pytest.raises(AppError) as raised:
        ConfigLoader().load(files.config_path)

    assert raised.value.error_type is ErrorType.CONFIGURATION
    assert raised.value.trace is True
    assert "timeout_seconds" in raised.value.diagnostic_message
    assert "retention_days" in raised.value.diagnostic_message
    assert "max_files_per_day" in raised.value.diagnostic_message


def test_load_invalid_retry_count_settings_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込IFが再試行回数の負数を拒否すること
    確認：generator.max_retriesとvalidator.max_retriesが負数の場合は設定不備として拒否されること
    """
    files = create_foundation_config(tmp_path)
    _replace_config_text(files.config_path, "  max_retries: 2", "  max_retries: -1")
    _replace_config_text(files.config_path, "  max_retries: 1", "  max_retries: -1")

    _assert_configuration_error(
        files.config_path,
        ("generator.max_retries", "validator.max_retries"),
    )


def test_load_treats_invalid_optional_ui_settings_as_empty(
    tmp_path: Path,
) -> None:
    """
    観点：任意UI設定の型不正が内部設定や秘密情報の公開へ波及しないこと
    確認：welcome_messageが文字列以外、input_suggestionsが文字列配列以外の場合は空扱いで読み込まれること
    """
    from backend.infrastructure.config.loader import ConfigLoader

    files = create_foundation_config(tmp_path)
    _replace_config_text(
        files.config_path, '  welcome_message: "ようこそ"', "  welcome_message: 123"
    )
    old_suggestions = (
        "  input_suggestions:\n"
        '    - "申請手順を確認したい"\n'
        '    - "参考資料の該当ページを知りたい"'
    )
    _replace_config_text(
        files.config_path,
        old_suggestions,
        '  input_suggestions:\n    - ["nested"]',
    )

    settings = ConfigLoader().load(files.config_path)

    assert settings.ui.welcome_message is None
    assert settings.ui.input_suggestions == ()


def test_load_invalid_timezone_raises_configuration_error(tmp_path: Path) -> None:
    """
    観点：設定読込IFがIANA timezone名を検証すること
    確認：app.timezoneに存在しないタイムゾーン名を指定した場合は設定不備として拒否されること
    """
    files = create_foundation_config(tmp_path, timezone="Invalid/Timezone")

    _assert_configuration_error(files.config_path, ("app.timezone",))


def test_load_empty_codex_docker_image_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込IFがCodex Dockerイメージ名の空文字を拒否すること
    確認：codex_docker.imageが空文字の場合はErrorType.CONFIGURATIONとなり、診断文に対象項目名が含まれること
    """
    files = create_foundation_config(tmp_path)
    _replace_config_text(
        files.config_path,
        '  image: "d-concierge-codex:latest"',
        '  image: ""',
    )

    _assert_configuration_error(files.config_path, ("codex_docker.image",))


def test_load_missing_generator_home_and_schema_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込IFが生成用Codexホームと出力スキーマの実体を検証すること
    確認：generator.homeとgenerator.output_schemaが存在しない場合は設定不備として拒否されること
    """
    files = create_foundation_config(tmp_path)
    _replace_config_text(
        files.config_path,
        files.generator_home_dir.as_posix(),
        (tmp_path / "missing_generator_home").as_posix(),
    )
    _replace_config_text(
        files.config_path,
        files.generator_output_schema.as_posix(),
        (tmp_path / "missing_schema" / "answer.json").as_posix(),
    )

    _assert_configuration_error(
        files.config_path,
        ("generator.home", "generator.output_schema"),
    )


def test_load_missing_validator_home_and_schema_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込IFが検証用Codexホームと出力スキーマの実体を検証すること
    確認：validator.homeとvalidator.output_schemaが存在しない場合は設定不備として拒否されること
    """
    files = create_foundation_config(tmp_path)
    _replace_config_text(
        files.config_path,
        files.validator_home_dir.as_posix(),
        (tmp_path / "missing_validator_home").as_posix(),
    )
    _replace_config_text(
        files.config_path,
        files.validator_output_schema.as_posix(),
        (tmp_path / "missing_schema" / "validator.json").as_posix(),
    )

    _assert_configuration_error(
        files.config_path,
        ("validator.home", "validator.output_schema"),
    )


def test_load_trace_log_dir_pointing_to_file_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込IFがトレースログ出力先をディレクトリとして検証すること
    確認：trace_log.dirが既存ファイルを指す場合は設定不備として拒否されること
    """
    files = create_foundation_config(tmp_path)
    trace_log_file = tmp_path / "trace-log-as-file"
    trace_log_file.write_text("not directory\n", encoding="utf-8")
    _replace_config_text(
        files.config_path,
        files.trace_log_dir.as_posix(),
        trace_log_file.as_posix(),
    )

    _assert_configuration_error(files.config_path, ("trace_log.dir",))


def test_load_startup_trace_log_settings_reads_valid_trace_settings(
    tmp_path: Path,
) -> None:
    """
    観点：設定読込失敗時向けの最小トレースログ設定を抽出できること
    確認：有効なconfig.yamlではtrace_log.dir、timezone、retention_days、max_files_per_dayが反映されること
    """
    from backend.infrastructure.config.loader import ConfigLoader

    files = create_foundation_config(tmp_path)

    settings = ConfigLoader().load_startup_trace_log_settings(
        files.config_path,
        tmp_path,
    )

    assert settings.dir == files.trace_log_dir.resolve()
    assert str(settings.timezone) == "Asia/Tokyo"
    assert settings.retention_days == 90
    assert settings.max_files_per_day == 1000


def test_load_startup_trace_log_settings_uses_defaults_when_config_is_unreadable(
    tmp_path: Path,
) -> None:
    """
    観点：config.yaml自体を読めない場合でも起動失敗ログの保存先を確保すること
    確認：存在しないconfig.yamlではfallbackディレクトリ、UTC、既定保持日数、既定最大件数を返すこと
    """
    from backend.infrastructure.config.loader import (
        DEFAULT_STARTUP_TRACE_MAX_FILES_PER_DAY,
        DEFAULT_STARTUP_TRACE_RETENTION_DAYS,
        ConfigLoader,
    )

    settings = ConfigLoader().load_startup_trace_log_settings(
        tmp_path / "missing-config.yaml",
        tmp_path,
    )

    assert settings.dir == (tmp_path / "trace_log_startup_errors").resolve()
    assert str(settings.timezone) == "UTC"
    assert settings.retention_days == DEFAULT_STARTUP_TRACE_RETENTION_DAYS
    assert settings.max_files_per_day == DEFAULT_STARTUP_TRACE_MAX_FILES_PER_DAY


def test_load_startup_trace_log_settings_uses_fallbacks_for_invalid_values(
    tmp_path: Path,
) -> None:
    """
    観点：起動失敗ログ設定の抽出が不正値に引きずられないこと
    確認：timezone不正、trace_log.dirが既存ファイル、保持日数と最大件数が0の場合は安全なfallback値を返すこと
    """
    from backend.infrastructure.config.loader import (
        DEFAULT_STARTUP_TRACE_MAX_FILES_PER_DAY,
        DEFAULT_STARTUP_TRACE_RETENTION_DAYS,
        ConfigLoader,
    )

    files = create_foundation_config(
        tmp_path,
        timezone="Invalid/Timezone",
        trace_retention_days=0,
        trace_max_files_per_day=0,
    )
    trace_log_file = tmp_path / "trace-log-as-file"
    trace_log_file.write_text("not directory\n", encoding="utf-8")
    _replace_config_text(
        files.config_path,
        files.trace_log_dir.as_posix(),
        trace_log_file.as_posix(),
    )

    settings = ConfigLoader().load_startup_trace_log_settings(
        files.config_path,
        tmp_path,
    )

    assert settings.dir == (tmp_path / "trace_log_startup_errors").resolve()
    assert str(settings.timezone) == "UTC"
    assert settings.retention_days == DEFAULT_STARTUP_TRACE_RETENTION_DAYS
    assert settings.max_files_per_day == DEFAULT_STARTUP_TRACE_MAX_FILES_PER_DAY


def test_load_startup_trace_log_settings_uses_fallback_when_trace_dir_is_missing(
    tmp_path: Path,
) -> None:
    """
    観点：trace_log.dir欠落時も起動失敗ログの保存先を確保すること
    確認：trace_log.dirを抽出できない場合は起動失敗用fallbackディレクトリを返すこと
    """
    from backend.infrastructure.config.loader import ConfigLoader

    files = create_foundation_config(tmp_path)
    _remove_config_line(
        files.config_path, f'  dir: "{files.trace_log_dir.as_posix()}"\n'
    )

    settings = ConfigLoader().load_startup_trace_log_settings(
        files.config_path,
        tmp_path,
    )

    assert settings.dir == (tmp_path / "trace_log_startup_errors").resolve()


def test_load_startup_trace_log_settings_uses_defaults_for_non_mapping_sections(
    tmp_path: Path,
) -> None:
    """
    観点：起動失敗ログ設定の抽出がセクション型不正に引きずられないこと
    確認：appとtrace_logがmappingではない場合はUTCと起動失敗用fallbackディレクトリを返すこと
    """
    from backend.infrastructure.config.loader import ConfigLoader

    config_path = tmp_path / "config.yaml"
    config_path.write_text("app: invalid\ntrace_log: invalid\n", encoding="utf-8")

    settings = ConfigLoader().load_startup_trace_log_settings(config_path, tmp_path)

    assert str(settings.timezone) == "UTC"
    assert settings.dir == (tmp_path / "trace_log_startup_errors").resolve()


def test_load_startup_trace_log_settings_uses_utc_for_non_string_timezone(
    tmp_path: Path,
) -> None:
    """
    観点：起動失敗ログ設定の抽出がtimezone型不正に引きずられないこと
    確認：app.timezoneが文字列ではない場合はUTCを返すこと
    """
    from backend.infrastructure.config.loader import ConfigLoader

    files = create_foundation_config(tmp_path)
    _replace_config_text(
        files.config_path, '  timezone: "Asia/Tokyo"', "  timezone: 123"
    )

    settings = ConfigLoader().load_startup_trace_log_settings(
        files.config_path,
        tmp_path,
    )

    assert str(settings.timezone) == "UTC"


def test_load_non_mapping_yaml_raises_configuration_error(tmp_path: Path) -> None:
    """
    観点：設定読込IFがYAMLルート構造の不正を検知すること
    確認：mappingではないconfig.yamlは設定不備として拒否されること
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- invalid\n", encoding="utf-8")

    _assert_configuration_error(config_path, ("config.yaml",))


def _assert_configuration_error(
    config_path: Path,
    expected_fields: tuple[str, ...],
) -> None:
    from backend.infrastructure.config.loader import ConfigLoader
    from backend.shared.errors.error_type import ErrorType
    from backend.shared.errors.errors import AppError

    with pytest.raises(AppError) as raised:
        ConfigLoader().load(config_path)

    assert raised.value.error_type is ErrorType.CONFIGURATION
    assert raised.value.trace is True
    for expected_field in expected_fields:
        assert expected_field in raised.value.diagnostic_message


def _remove_config_line(config_path: Path, line_to_remove: str) -> None:
    config_text = config_path.read_text(encoding="utf-8")
    assert line_to_remove in config_text
    config_path.write_text(
        config_text.replace(line_to_remove, "", 1),
        encoding="utf-8",
    )


def _remove_config_line_by_prefix(config_path: Path, line_prefix: str) -> None:
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated_lines = []
    removed = False
    for line in lines:
        if not removed and line.startswith(line_prefix):
            removed = True
            continue
        updated_lines.append(line)
    assert removed
    config_path.write_text("".join(updated_lines), encoding="utf-8")


def _replace_config_text(config_path: Path, old: str, new: str) -> None:
    config_text = config_path.read_text(encoding="utf-8")
    assert old in config_text
    config_path.write_text(config_text.replace(old, new, 1), encoding="utf-8")


def _remove_required_nested_setting(
    files: FoundationConfigFiles,
    expected_field: str,
) -> None:
    match expected_field:
        case "generator.max_retries":
            line_to_remove = "  max_retries: 2\n"
        case "generator.home":
            line_to_remove = f'  home: "{files.generator_home_dir.as_posix()}"\n'
        case "generator.workdir":
            line_to_remove = f'  workdir: "{files.generator_workdir.as_posix()}"\n'
        case "generator.output_schema":
            line_to_remove = (
                f'  output_schema: "{files.generator_output_schema.as_posix()}"\n'
            )
        case "generator.saved_artifacts_dir":
            line_to_remove = (
                f'  saved_artifacts_dir: "{files.saved_artifacts_dir.as_posix()}"\n'
            )
        case "validator.max_retries":
            line_to_remove = "  max_retries: 1\n"
        case "validator.home":
            line_to_remove = f'  home: "{files.validator_home_dir.as_posix()}"\n'
        case "validator.workdir":
            line_to_remove = f'  workdir: "{files.validator_workdir.as_posix()}"\n'
        case "validator.output_schema":
            line_to_remove = (
                f'  output_schema: "{files.validator_output_schema.as_posix()}"\n'
            )
        case "codex_docker.image":
            line_to_remove = '  image: "d-concierge-codex:latest"\n'
        case "codex_docker.workspace_dir":
            line_to_remove = '  workspace_dir: "/workspace"\n'
        case "codex_docker.codex_home_dir":
            line_to_remove = '  codex_home_dir: "/codex-home"\n'
        case "codex_docker.codex_api_key":
            line_to_remove = '  codex_api_key: ""\n'
        case "server.timeout_seconds":
            line_to_remove = "  timeout_seconds: 120\n"
        case "trace_log.dir":
            line_to_remove = f'  dir: "{files.trace_log_dir.as_posix()}"\n'
        case "trace_log.retention_days":
            line_to_remove = "  retention_days: 90\n"
        case "trace_log.max_files_per_day":
            line_to_remove = "  max_files_per_day: 1000\n"
        case _:
            raise AssertionError(f"未対応の必須設定項目です: {expected_field}")

    _remove_config_line(files.config_path, line_to_remove)

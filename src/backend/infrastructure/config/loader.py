from collections.abc import Mapping, Sequence
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

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

type YamlScalar = str | int | float | bool | None
type YamlValue = YamlScalar | Mapping[str, YamlValue] | Sequence[YamlValue]


class ConfigLoader:
    """YAML設定を型付き設定へ変換する。"""

    @staticmethod
    def load(config_path: Path, base_dir: Path | None = None) -> AppConfig:
        """設定ファイルを読み込み、必須項目と数値範囲を検証した設定を返す。"""
        root = (base_dir if base_dir is not None else config_path.parent).resolve()
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise _configuration_error("設定ファイルを読み込めません。", exc) from exc
        except yaml.YAMLError as exc:
            raise _configuration_error("設定ファイルの形式が不正です。", exc) from exc

        if not isinstance(loaded, Mapping):
            raise _configuration_error("設定ファイルのルート形式が不正です。")

        data: Mapping[str, YamlValue] = loaded
        app_timezone = _required_timezone(data, ("app", "timezone"))

        timeout_seconds = _required_int(data, ("server", "timeout_seconds"))
        if timeout_seconds <= 0:
            raise _configuration_error("タイムアウト設定が不正です。")

        generator_max_retries = _required_int(data, ("generator", "max_retries"))
        if generator_max_retries < 0:
            raise _configuration_error("生成再試行上限が不正です。")

        validator_max_retries = _required_int(data, ("validator", "max_retries"))
        if validator_max_retries < 0:
            raise _configuration_error("検証再出力上限が不正です。")

        trace_log_retention_days = _required_int(data, ("trace_log", "retention_days"))
        if trace_log_retention_days <= 0:
            raise _configuration_error("必須設定 trace_log.retention_days が不正です。")

        trace_log_max_files_per_day = _required_int(
            data, ("trace_log", "max_files_per_day")
        )
        if trace_log_max_files_per_day <= 0:
            raise _configuration_error(
                "必須設定 trace_log.max_files_per_day が不正です。"
            )

        return AppConfig(
            app=AppRuntimeConfig(timezone=app_timezone),
            ui=UiConfig(
                welcome_message=_optional_str(data, ("ui", "welcome_message")),
                sub_welcome_message=_optional_str(data, ("ui", "sub_welcome_message")),
                input_suggestions=tuple(
                    _optional_str_list(data, ("ui", "input_suggestions"))
                ),
            ),
            data_source_dir=_path(root, _required_str(data, ("data_source", "dir"))),
            generator=GeneratorConfig(
                max_retries=generator_max_retries,
                home=_path(root, _required_str(data, ("generator", "home"))),
                workdir=_path(root, _required_str(data, ("generator", "workdir"))),
                output_schema=_path(
                    root, _required_str(data, ("generator", "output_schema"))
                ),
                saved_artifacts_dir=_path(
                    root, _required_str(data, ("generator", "saved_artifacts_dir"))
                ),
            ),
            validator=ValidatorConfig(
                max_retries=validator_max_retries,
                home=_path(root, _required_str(data, ("validator", "home"))),
                workdir=_path(root, _required_str(data, ("validator", "workdir"))),
                output_schema=_path(
                    root, _required_str(data, ("validator", "output_schema"))
                ),
            ),
            codex_docker=CodexDockerConfig(
                image=_required_str(data, ("codex_docker", "image")),
                workspace_dir=_required_str(data, ("codex_docker", "workspace_dir")),
                codex_home_dir=_required_str(data, ("codex_docker", "codex_home_dir")),
                codex_api_key=_required_present_str(
                    data, ("codex_docker", "codex_api_key")
                ),
            ),
            database=DatabaseConfig(url=_required_str(data, ("database", "url"))),
            server=ServerConfig(timeout_seconds=timeout_seconds),
            trace_log=TraceLogConfig(
                dir=_path(root, _required_str(data, ("trace_log", "dir"))),
                retention_days=trace_log_retention_days,
                max_files_per_day=trace_log_max_files_per_day,
            ),
        )


def _path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _nested(data: Mapping[str, YamlValue], path: tuple[str, ...]) -> YamlValue:
    current: YamlValue = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            dotted = ".".join(path)
            raise _configuration_error(f"必須設定 {dotted} が不足しています。")
        current = current[key]
    return current


def _required_str(data: Mapping[str, YamlValue], path: tuple[str, ...]) -> str:
    value = _nested(data, path)
    if not isinstance(value, str) or value.strip() == "":
        dotted = ".".join(path)
        raise _configuration_error(f"必須設定 {dotted} が不正です。")
    return value


def _required_present_str(data: Mapping[str, YamlValue], path: tuple[str, ...]) -> str:
    value = _nested(data, path)
    if not isinstance(value, str):
        dotted = ".".join(path)
        raise _configuration_error(f"必須設定 {dotted} が不正です。")
    return value


def _optional_str(data: Mapping[str, YamlValue], path: tuple[str, ...]) -> str | None:
    try:
        value = _nested(data, path)
    except AppError:
        return None
    if value is None:
        return None
    if not isinstance(value, str):
        dotted = ".".join(path)
        raise _configuration_error(f"任意設定 {dotted} が不正です。")
    return value


def _required_int(data: Mapping[str, YamlValue], path: tuple[str, ...]) -> int:
    value = _nested(data, path)
    if type(value) is not int:
        dotted = ".".join(path)
        raise _configuration_error(f"必須設定 {dotted} が不正です。")
    return value


def _required_timezone(
    data: Mapping[str, YamlValue], path: tuple[str, ...]
) -> ZoneInfo:
    timezone_name = _required_str(data, path)
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        dotted = ".".join(path)
        raise _configuration_error(f"必須設定 {dotted} が不正です。", exc) from exc


def _optional_str_list(
    data: Mapping[str, YamlValue], path: tuple[str, ...]
) -> list[str]:
    try:
        value = _nested(data, path)
    except AppError:
        return []
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        dotted = ".".join(path)
        raise _configuration_error(f"任意設定 {dotted} が不正です。")
    suggestions: list[str] = []
    for item in value:
        if not isinstance(item, str):
            dotted = ".".join(path)
            raise _configuration_error(f"任意設定 {dotted} が不正です。")
        suggestions.append(item)
    return suggestions


def _configuration_error(
    diagnostic_message: str, cause: Exception | None = None
) -> AppError:
    return AppError(
        ErrorType.CONFIGURATION,
        trace=True,
        diagnostic_message=diagnostic_message,
        cause=cause,
    )

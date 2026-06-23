from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from yaml import YAMLError
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from backend.infrastructure.config.settings import (
    AppSectionSettings,
    AppSettings,
    CodexDockerSectionSettings,
    CodexWorkerSectionSettings,
    DatabaseSectionSettings,
    DataSourceSectionSettings,
    ServerSectionSettings,
    StartupTraceLogSettings,
    TraceLogSectionSettings,
    UiSectionSettings,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

type ConfigValue = str | int | list[str] | dict[str, ConfigValue] | None
type ConfigMap = dict[str, ConfigValue]

DEFAULT_STARTUP_TRACE_RETENTION_DAYS = 90
DEFAULT_STARTUP_TRACE_MAX_FILES_PER_DAY = 1000


@dataclass(frozen=True, slots=True)
class ParsedConfigSections:
    """config.yamlの主要セクション。"""

    app: ConfigMap
    ui: ConfigMap
    data_source: ConfigMap
    generator: ConfigMap
    validator: ConfigMap
    codex_docker: ConfigMap
    database: ConfigMap
    server: ConfigMap
    trace_log: ConfigMap


class ConfigLoader:
    """config.yamlを型付き設定へ変換するローダー。"""

    def load(self, config_path: Path, base_dir: Path | None = None) -> AppSettings:
        """設定ファイルを読み込み、起動前検証済み設定を返す。"""

        effective_base_dir = base_dir if base_dir is not None else config_path.parent
        yaml_config = self._parse_config(config_path)
        problems: list[str] = []
        sections = self._sections(yaml_config, problems)

        timezone_name = self._required_string(
            sections.app,
            "app.timezone",
            problems,
        )
        timezone = self._load_timezone(timezone_name, problems)

        data_source_dir = self._resolve_path(
            self._required_path(sections.data_source, "data_source.dir", problems),
            effective_base_dir,
        )
        generator_home = self._resolve_path(
            self._required_path(sections.generator, "generator.home", problems),
            effective_base_dir,
        )
        generator_workdir = self._resolve_path(
            self._required_path(sections.generator, "generator.workdir", problems),
            effective_base_dir,
        )
        generator_output_schema = self._resolve_path(
            self._required_path(
                sections.generator,
                "generator.output_schema",
                problems,
            ),
            effective_base_dir,
        )
        saved_artifacts_dir = self._resolve_path(
            self._required_path(
                sections.generator,
                "generator.saved_artifacts_dir",
                problems,
            ),
            effective_base_dir,
        )
        validator_home = self._resolve_path(
            self._required_path(sections.validator, "validator.home", problems),
            effective_base_dir,
        )
        validator_workdir = self._resolve_path(
            self._required_path(sections.validator, "validator.workdir", problems),
            effective_base_dir,
        )
        validator_output_schema = self._resolve_path(
            self._required_path(
                sections.validator,
                "validator.output_schema",
                problems,
            ),
            effective_base_dir,
        )
        trace_log_dir = self._resolve_path(
            self._required_path(sections.trace_log, "trace_log.dir", problems),
            effective_base_dir,
        )

        generator_max_retries = self._required_int(
            sections.generator,
            "generator.max_retries",
            problems,
        )
        validator_max_retries = self._required_int(
            sections.validator,
            "validator.max_retries",
            problems,
        )
        server_timeout_seconds = self._required_int(
            sections.server,
            "server.timeout_seconds",
            problems,
        )
        trace_retention_days = self._required_int(
            sections.trace_log,
            "trace_log.retention_days",
            problems,
        )
        trace_max_files_per_day = self._required_int(
            sections.trace_log,
            "trace_log.max_files_per_day",
            problems,
        )
        codex_image = self._required_string(
            sections.codex_docker,
            "codex_docker.image",
            problems,
        )
        workspace_dir = self._required_string(
            sections.codex_docker,
            "codex_docker.workspace_dir",
            problems,
        )
        codex_home_dir = self._required_string(
            sections.codex_docker,
            "codex_docker.codex_home_dir",
            problems,
        )
        codex_api_key = self._required_string(
            sections.codex_docker,
            "codex_docker.codex_api_key",
            problems,
            allow_empty=True,
        )
        database_url = self._required_string(
            sections.database,
            "database.url",
            problems,
        )

        self._validate_positive(
            "server.timeout_seconds",
            server_timeout_seconds,
            problems,
        )
        self._validate_positive(
            "trace_log.retention_days",
            trace_retention_days,
            problems,
        )
        self._validate_positive(
            "trace_log.max_files_per_day",
            trace_max_files_per_day,
            problems,
        )
        self._validate_non_negative(
            "generator.max_retries",
            generator_max_retries,
            problems,
        )
        self._validate_non_negative(
            "validator.max_retries",
            validator_max_retries,
            problems,
        )
        self._validate_directory("data_source.dir", data_source_dir, problems)
        self._validate_codex_home("generator.home", generator_home, problems)
        self._validate_directory("generator.workdir", generator_workdir, problems)
        self._validate_file(
            "generator.output_schema",
            generator_output_schema,
            problems,
        )
        self._validate_directory(
            "generator.saved_artifacts_dir",
            saved_artifacts_dir,
            problems,
        )
        self._validate_codex_home("validator.home", validator_home, problems)
        self._validate_directory("validator.workdir", validator_workdir, problems)
        self._validate_file(
            "validator.output_schema",
            validator_output_schema,
            problems,
        )
        self._validate_directory("trace_log.dir", trace_log_dir, problems)

        if problems:
            self._raise_configuration_error(problems)

        return AppSettings(
            app=AppSectionSettings(timezone=timezone),
            ui=UiSectionSettings(
                welcome_message=self._optional_string(
                    sections.ui,
                    "welcome_message",
                ),
                sub_welcome_message=self._optional_string(
                    sections.ui,
                    "sub_welcome_message",
                ),
                input_suggestions=self._optional_string_tuple(
                    sections.ui,
                    "input_suggestions",
                ),
            ),
            data_source=DataSourceSectionSettings(dir=data_source_dir),
            generator=CodexWorkerSectionSettings(
                max_retries=generator_max_retries,
                home=generator_home,
                workdir=generator_workdir,
                output_schema=generator_output_schema,
                saved_artifacts_dir=saved_artifacts_dir,
            ),
            validator=CodexWorkerSectionSettings(
                max_retries=validator_max_retries,
                home=validator_home,
                workdir=validator_workdir,
                output_schema=validator_output_schema,
            ),
            codex_docker=CodexDockerSectionSettings(
                image=codex_image,
                workspace_dir=workspace_dir,
                codex_home_dir=codex_home_dir,
                codex_api_key=codex_api_key,
            ),
            database=DatabaseSectionSettings(url=database_url),
            server=ServerSectionSettings(timeout_seconds=server_timeout_seconds),
            trace_log=TraceLogSectionSettings(
                dir=trace_log_dir,
                retention_days=trace_retention_days,
                max_files_per_day=trace_max_files_per_day,
            ),
        )

    def load_startup_trace_log_settings(
        self,
        config_path: Path,
        base_dir: Path | None = None,
    ) -> StartupTraceLogSettings:
        """設定読込失敗時にも使えるトレースログ設定を抽出する。"""

        effective_base_dir = base_dir if base_dir is not None else config_path.parent
        fallback_dir = (effective_base_dir / "trace_log_startup_errors").resolve()
        try:
            yaml_config = self._parse_config(config_path)
        except AppError:
            return StartupTraceLogSettings(
                dir=fallback_dir,
                timezone=ZoneInfo("UTC"),
                retention_days=DEFAULT_STARTUP_TRACE_RETENTION_DAYS,
                max_files_per_day=DEFAULT_STARTUP_TRACE_MAX_FILES_PER_DAY,
            )

        app_section = self._optional_section(yaml_config, "app")
        trace_log_section = self._optional_section(yaml_config, "trace_log")
        timezone = self._optional_timezone(app_section, "timezone")
        trace_dir = self._startup_trace_dir(
            trace_log_section,
            effective_base_dir,
            fallback_dir,
        )
        return StartupTraceLogSettings(
            dir=trace_dir,
            timezone=timezone,
            retention_days=self._optional_positive_int(
                trace_log_section,
                "retention_days",
                DEFAULT_STARTUP_TRACE_RETENTION_DAYS,
            ),
            max_files_per_day=self._optional_positive_int(
                trace_log_section,
                "max_files_per_day",
                DEFAULT_STARTUP_TRACE_MAX_FILES_PER_DAY,
            ),
        )

    def _parse_config(self, config_path: Path) -> ConfigMap:
        try:
            yaml_node = yaml.compose(config_path.read_text(encoding="utf-8"))
        except (OSError, YAMLError) as error:
            self._raise_configuration_error((str(config_path),), error)
        if not isinstance(yaml_node, MappingNode):
            self._raise_configuration_error(("config.yaml",))
        return self._mapping_from_node(yaml_node)

    def _mapping_from_node(self, node: MappingNode) -> ConfigMap:
        result: ConfigMap = {}
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                continue
            result[key_node.value] = self._value_from_node(value_node)
        return result

    def _value_from_node(self, node: Node) -> ConfigValue:
        if isinstance(node, MappingNode):
            return self._mapping_from_node(node)
        if isinstance(node, SequenceNode):
            return self._sequence_from_node(node)
        if isinstance(node, ScalarNode):
            if node.tag.endswith(":null"):
                return None
            if node.tag.endswith(":int"):
                try:
                    return int(node.value)
                except ValueError:
                    return str(node.value)
            return str(node.value)
        return None

    def _sequence_from_node(self, node: SequenceNode) -> list[str]:
        values: list[str] = []
        for child_node in node.value:
            if isinstance(child_node, ScalarNode):
                values.append(child_node.value)
        return values

    def _sections(
        self, yaml_config: ConfigMap, problems: list[str]
    ) -> ParsedConfigSections:
        return ParsedConfigSections(
            app=self._required_section(yaml_config, "app", ("app.timezone",), problems),
            ui=self._optional_section(yaml_config, "ui"),
            data_source=self._required_section(
                yaml_config,
                "data_source",
                ("data_source.dir",),
                problems,
            ),
            generator=self._required_section(
                yaml_config,
                "generator",
                (
                    "generator.max_retries",
                    "generator.home",
                    "generator.workdir",
                    "generator.output_schema",
                    "generator.saved_artifacts_dir",
                ),
                problems,
            ),
            validator=self._required_section(
                yaml_config,
                "validator",
                (
                    "validator.max_retries",
                    "validator.home",
                    "validator.workdir",
                    "validator.output_schema",
                ),
                problems,
            ),
            codex_docker=self._required_section(
                yaml_config,
                "codex_docker",
                (
                    "codex_docker.image",
                    "codex_docker.workspace_dir",
                    "codex_docker.codex_home_dir",
                    "codex_docker.codex_api_key",
                ),
                problems,
            ),
            database=self._required_section(
                yaml_config,
                "database",
                ("database.url",),
                problems,
            ),
            server=self._required_section(
                yaml_config,
                "server",
                ("server.timeout_seconds",),
                problems,
            ),
            trace_log=self._required_section(
                yaml_config,
                "trace_log",
                (
                    "trace_log.dir",
                    "trace_log.retention_days",
                    "trace_log.max_files_per_day",
                ),
                problems,
            ),
        )

    def _required_section(
        self,
        yaml_config: ConfigMap,
        section_name: str,
        required_fields: tuple[str, ...],
        problems: list[str],
    ) -> ConfigMap:
        value = yaml_config.get(section_name)
        if isinstance(value, dict):
            return value
        problems.extend(required_fields)
        return {}

    def _optional_section(self, yaml_config: ConfigMap, section_name: str) -> ConfigMap:
        value = yaml_config.get(section_name)
        if isinstance(value, dict):
            return value
        return {}

    def _required_string(
        self,
        section: ConfigMap,
        field_path: str,
        problems: list[str],
        *,
        allow_empty: bool = False,
    ) -> str:
        value = section.get(self._field_name(field_path))
        if not isinstance(value, str):
            problems.append(field_path)
            return ""
        if not allow_empty and not value.strip():
            problems.append(field_path)
        return value

    def _optional_string(self, section: ConfigMap, field_name: str) -> str | None:
        value = section.get(field_name)
        if isinstance(value, str):
            return value
        return None

    def _optional_string_tuple(
        self,
        section: ConfigMap,
        field_name: str,
    ) -> tuple[str, ...]:
        value = section.get(field_name)
        if isinstance(value, list):
            return tuple(value)
        return ()

    def _required_path(
        self,
        section: ConfigMap,
        field_path: str,
        problems: list[str],
    ) -> Path:
        value = self._required_string(section, field_path, problems)
        return Path(value)

    def _required_int(
        self,
        section: ConfigMap,
        field_path: str,
        problems: list[str],
    ) -> int:
        value = section.get(self._field_name(field_path))
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append(field_path)
            return 0
        return value

    def _field_name(self, field_path: str) -> str:
        return field_path.rsplit(".", maxsplit=1)[-1]

    def _load_timezone(self, timezone_name: str, problems: list[str]) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name)
        except ValueError, ZoneInfoNotFoundError:
            problems.append("app.timezone")
            return ZoneInfo("UTC")

    def _optional_timezone(self, section: ConfigMap, field_name: str) -> ZoneInfo:
        value = section.get(field_name)
        if not isinstance(value, str):
            return ZoneInfo("UTC")
        try:
            return ZoneInfo(value)
        except ValueError, ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    def _optional_positive_int(
        self,
        section: ConfigMap,
        field_name: str,
        default_value: int,
    ) -> int:
        value = section.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return default_value
        return value

    def _startup_trace_dir(
        self,
        section: ConfigMap,
        base_dir: Path,
        fallback_dir: Path,
    ) -> Path:
        value = section.get("dir")
        if not isinstance(value, str) or not value.strip():
            return fallback_dir
        configured_dir = self._resolve_path(Path(value), base_dir)
        if configured_dir.exists() and not configured_dir.is_dir():
            return fallback_dir
        return configured_dir

    def _resolve_path(self, path: Path, base_dir: Path) -> Path:
        if path.is_absolute():
            return path.resolve()
        return (base_dir / path).resolve()

    def _validate_positive(
        self,
        field_name: str,
        value: int,
        problems: list[str],
    ) -> None:
        if value <= 0:
            problems.append(field_name)

    def _validate_non_negative(
        self,
        field_name: str,
        value: int,
        problems: list[str],
    ) -> None:
        if value < 0:
            problems.append(field_name)

    def _validate_directory(
        self,
        field_name: str,
        path: Path,
        problems: list[str],
    ) -> None:
        if not path.exists() or not path.is_dir():
            problems.append(field_name)

    def _validate_file(
        self,
        field_name: str,
        path: Path,
        problems: list[str],
    ) -> None:
        if not path.exists() or not path.is_file():
            problems.append(field_name)

    def _validate_codex_home(
        self,
        field_name: str,
        path: Path,
        problems: list[str],
    ) -> None:
        if not path.exists() or not path.is_dir() or not (path / "AGENTS.md").is_file():
            problems.append(field_name)

    def _raise_configuration_error(
        self,
        fields: Iterable[str],
        cause: BaseException | None = None,
    ) -> NoReturn:
        diagnostic_fields = self._unique_fields(fields)
        diagnostic_message = "設定不備: " + ", ".join(diagnostic_fields)
        raise AppError(
            error_type=ErrorType.CONFIGURATION,
            trace=True,
            diagnostic_message=diagnostic_message,
            cause=cause,
        )

    def _unique_fields(self, fields: Iterable[str]) -> tuple[str, ...]:
        unique_fields: list[str] = []
        for field in fields:
            if field not in unique_fields:
                unique_fields.append(field)
        return tuple(unique_fields)

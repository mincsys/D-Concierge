from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from os import environ
from pathlib import Path
from textwrap import dedent

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError


@dataclass(frozen=True, slots=True)
class FoundationConfigFiles:
    root_dir: Path
    config_path: Path
    data_source_dir: Path
    generator_home_dir: Path
    generator_workdir: Path
    generator_output_schema: Path
    saved_artifacts_dir: Path
    validator_home_dir: Path
    validator_workdir: Path
    validator_output_schema: Path
    trace_log_dir: Path


@dataclass(frozen=True, slots=True)
class AuthenticatedSessionSeed:
    user_id: str
    user_name: str
    token: str
    token_hash: str
    expires_at: datetime


DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://d_concierge_test:d_concierge_test@127.0.0.1:55432/"
    "d_concierge_test"
)
TEST_DATABASE_NAME = "d_concierge_test"
TEST_DATABASE_USER = "d_concierge_test"
TEST_DATABASE_PORT = 55432
LOGIN_SESSION_COOKIE_NAME = "d_concierge_session"
VALID_SESSION_TOKEN = "valid-session-token"


def create_foundation_config(
    root_dir: Path,
    *,
    timezone: str = "Asia/Tokyo",
    database_url: str = "postgresql+psycopg://user:password@localhost:5432/d_concierge",
    timeout_seconds: int = 120,
    trace_retention_days: int = 90,
    trace_max_files_per_day: int = 1000,
    include_ui: bool = True,
) -> FoundationConfigFiles:
    paths = FoundationConfigFiles(
        root_dir=root_dir,
        config_path=root_dir / "config.yaml",
        data_source_dir=root_dir / "data_source",
        generator_home_dir=root_dir / "codex" / "generator_home",
        generator_workdir=root_dir / "codex" / "sessions",
        generator_output_schema=root_dir / "schemas" / "answer.json",
        saved_artifacts_dir=root_dir / "codex" / "saved_artifacts",
        validator_home_dir=root_dir / "codex" / "validator_home",
        validator_workdir=root_dir / "codex" / "sessions_validator",
        validator_output_schema=root_dir / "schemas" / "validator.json",
        trace_log_dir=root_dir / "trace_log",
    )

    _prepare_foundation_paths(paths)
    paths.config_path.write_text(
        _foundation_config_text(
            paths,
            timezone=timezone,
            database_url=database_url,
            timeout_seconds=timeout_seconds,
            trace_retention_days=trace_retention_days,
            trace_max_files_per_day=trace_max_files_per_day,
            include_ui=include_ui,
        ),
        encoding="utf-8",
    )
    return paths


def foundation_test_database_url() -> str:
    return environ.get("D_CONCIERGE_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def foundation_migrations_dir() -> Path:
    return Path("src/backend/infrastructure/database/migrations")


def prepare_foundation_database(database_url: str) -> None:
    migrations_dir = foundation_migrations_dir()
    assert migrations_dir.exists(), "マイグレーションディレクトリがありません"

    _validate_foundation_test_database_url(database_url)
    engine = create_engine(database_url)
    try:
        _reset_public_schema(engine)
    finally:
        engine.dispose()
    upgrade_foundation_schema(database_url)


def upgrade_foundation_schema(database_url: str) -> None:
    migrations_dir = foundation_migrations_dir()
    assert migrations_dir.exists(), "マイグレーションディレクトリがありません"

    alembic_config = Config(str(migrations_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(migrations_dir))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")


def seed_authenticated_session(
    database_url: str,
    *,
    token_hash: str,
    token: str = VALID_SESSION_TOKEN,
) -> AuthenticatedSessionSeed:
    seed = AuthenticatedSessionSeed(
        user_id="user-001",
        user_name="テストユーザ",
        token=token,
        token_hash=token_hash,
        expires_at=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
    )
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine, only=("users", "login_sessions"))
        users = metadata.tables["users"]
        login_sessions = metadata.tables["login_sessions"]
        _insert_authenticated_session_rows(engine, users, login_sessions, seed)
    finally:
        engine.dispose()
    return seed


def expected_foundation_table_names() -> tuple[str, ...]:
    return (
        "users",
        "login_sessions",
        "chats",
        "chat_runs",
        "user_instructions",
        "intermediate_messages",
        "answer_blocks",
        "references",
        "artifacts",
    )


def _reset_public_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO public"))


def _validate_foundation_test_database_url(database_url: str) -> None:
    try:
        url = make_url(database_url)
    except ArgumentError as exception:
        raise RuntimeError("結合テスト用DBの接続先URLを解析できません。") from exception

    violations: list[str] = []
    if url.get_backend_name() != "postgresql":
        violations.append("DB種別がpostgresqlではありません")
    if url.database != TEST_DATABASE_NAME:
        violations.append(f"DB名が{TEST_DATABASE_NAME}ではありません")
    if url.username != TEST_DATABASE_USER:
        violations.append(f"ユーザが{TEST_DATABASE_USER}ではありません")
    if url.port != TEST_DATABASE_PORT:
        violations.append(f"ポートが{TEST_DATABASE_PORT}ではありません")
    if violations:
        raise RuntimeError(
            "結合テスト用DBではない接続先のためスキーマ初期化を拒否しました: "
            + "、".join(violations)
        )


def _insert_authenticated_session_rows(
    engine: Engine,
    users: Table,
    login_sessions: Table,
    seed: AuthenticatedSessionSeed,
) -> None:
    now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                id=seed.user_id,
                user_name=seed.user_name,
                password_hash="hashed-password",
                user_state="active",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            login_sessions.insert().values(
                token_hash=seed.token_hash,
                user_id=seed.user_id,
                expires_at=seed.expires_at,
                created_at=now,
                updated_at=now,
            )
        )


def _prepare_foundation_paths(paths: FoundationConfigFiles) -> None:
    directories = (
        paths.data_source_dir,
        paths.generator_home_dir,
        paths.generator_workdir,
        paths.saved_artifacts_dir,
        paths.validator_home_dir,
        paths.validator_workdir,
        paths.generator_output_schema.parent,
        paths.trace_log_dir,
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    for home_dir in (paths.generator_home_dir, paths.validator_home_dir):
        (home_dir / "AGENTS.md").write_text("テスト用Codexホーム\n", encoding="utf-8")

    paths.generator_output_schema.write_text('{"type":"object"}\n', encoding="utf-8")
    paths.validator_output_schema.write_text('{"type":"object"}\n', encoding="utf-8")


def _foundation_config_text(
    paths: FoundationConfigFiles,
    *,
    timezone: str,
    database_url: str,
    timeout_seconds: int,
    trace_retention_days: int,
    trace_max_files_per_day: int,
    include_ui: bool,
) -> str:
    ui_block = ""
    if include_ui:
        ui_block = dedent(
            """
            ui:
              welcome_message: "ようこそ"
              sub_welcome_message: "必要な資料を指定してください"
              input_suggestions:
                - "申請手順を確認したい"
                - "参考資料の該当ページを知りたい"
            """
        ).strip()

    config_blocks = (
        dedent(
            f"""
            app:
              timezone: "{timezone}"
            """
        ).strip(),
        ui_block,
        dedent(
            f"""
            data_source:
              dir: "{paths.data_source_dir.as_posix()}"
            generator:
              max_retries: 2
              home: "{paths.generator_home_dir.as_posix()}"
              workdir: "{paths.generator_workdir.as_posix()}"
              output_schema: "{paths.generator_output_schema.as_posix()}"
              saved_artifacts_dir: "{paths.saved_artifacts_dir.as_posix()}"
            validator:
              max_retries: 1
              home: "{paths.validator_home_dir.as_posix()}"
              workdir: "{paths.validator_workdir.as_posix()}"
              output_schema: "{paths.validator_output_schema.as_posix()}"
            codex_docker:
              image: "d-concierge-codex:latest"
              workspace_dir: "/workspace"
              codex_home_dir: "/codex-home"
              codex_api_key: ""
            database:
              url: "{database_url}"
            server:
              timeout_seconds: {timeout_seconds}
            trace_log:
              dir: "{paths.trace_log_dir.as_posix()}"
              retention_days: {trace_retention_days}
              max_files_per_day: {trace_max_files_per_day}
            """
        ).strip(),
    )
    return "\n".join(block for block in config_blocks if block) + "\n"

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

_DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "d_concierge_test:d_concierge_test@127.0.0.1:55432/d_concierge_test"
)


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    """結合テスト用PostgreSQL接続URLを返す。"""
    database_url = os.environ.get(
        "D_CONCIERGE_TEST_DATABASE_URL", _DEFAULT_TEST_DATABASE_URL
    )
    os.environ["D_CONCIERGE_TEST_DATABASE_URL"] = database_url
    return database_url


@pytest.fixture(scope="session")
def integration_database_name(integration_database_url: str) -> str:
    """結合テスト用PostgreSQLのDB名を返す。"""
    database_name = make_url(integration_database_url).database
    if database_name is None:
        pytest.fail("PostgreSQLテストDBのDB名を接続URLから取得できません。")
    return database_name


@pytest.fixture(scope="session")
def integration_database_engine(
    integration_database_url: str,
) -> Iterator[Engine]:
    """migration適用済みの結合テスト用PostgreSQL Engineを提供する。"""
    engine = create_engine(integration_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError as exc:
        pytest.fail(
            "PostgreSQLテストDBへ接続できません。"
            " `docker compose -f infra/compose.yml up -d postgres-test` を"
            "実行してください。"
            f" 接続先: {integration_database_url}"
            f" 詳細: {exc}"
        )

    previous_database_url = os.environ.get("D_CONCIERGE_DATABASE_URL")
    os.environ["D_CONCIERGE_DATABASE_URL"] = integration_database_url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("D_CONCIERGE_DATABASE_URL", None)
        else:
            os.environ["D_CONCIERGE_DATABASE_URL"] = previous_database_url

    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_integration_database(integration_database_engine: Engine) -> None:
    """各結合テスト前にPostgreSQLテストDBを既知状態へ戻す。"""
    with integration_database_engine.begin() as connection:
        table_list = connection.execute(
            text(
                """
                select string_agg(format('%I.%I', schemaname, tablename), ', ')
                from pg_tables
                where schemaname = 'public'
                  and tablename <> 'alembic_version'
                """
            )
        ).scalar_one()
        if table_list:
            connection.execute(
                text(f"truncate table {table_list} restart identity cascade")
            )

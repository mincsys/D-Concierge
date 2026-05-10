import os
from importlib import import_module
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.sql.schema import MetaData

from backend.infrastructure.database.models.base import Base

import_module("backend.infrastructure.database.models.chat")
import_module("backend.infrastructure.database.models.answer")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata: MetaData | None = Base.metadata


def _database_url() -> str:
    environment_url = os.environ.get("D_CONCIERGE_DATABASE_URL")
    if not environment_url:
        raise RuntimeError("D_CONCIERGE_DATABASE_URL が設定されていません。")
    return environment_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        raise RuntimeError("Alembic設定セクションが存在しません。")

    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _run_migrations_with_connection(connection)


def _run_migrations_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

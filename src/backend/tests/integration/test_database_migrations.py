from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID

import pytest
from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.dml import Insert

from backend.tests.support import foundation
from backend.tests.support.foundation import (
    expected_foundation_table_names,
    foundation_test_database_url,
    prepare_foundation_database,
)


class ReferenceLocatorPayload(TypedDict):
    path: str
    page_start: int
    page_end: int


def test_migrations_create_foundation_schema() -> None:
    """
    観点：DBマイグレーションが物理データ設計の基盤スキーマを作成すること
    確認：PostgreSQLテストDBへmigrationを適用すると、
    F001対象テーブル、列、主要索引がinspect結果に存在すること
    """
    database_url = foundation_test_database_url()

    prepare_foundation_database(database_url)
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        table_names = tuple(inspector.get_table_names())
        for expected_table_name in expected_foundation_table_names():
            assert expected_table_name in table_names
        assert "alembic_version" in table_names
        assert _inspected_column_names(inspector, "users") == (
            "id",
            "user_name",
            "password_hash",
            "user_state",
            "created_at",
            "updated_at",
        )
        assert _inspected_column_names(inspector, "chat_runs") == (
            "id",
            "chat_id",
            "state",
            "started_at",
            "execution_deadline_at",
            "ended_at",
            "user_message",
        )
        assert "chat_runs_one_unfinished_per_chat" in _inspected_index_names(
            inspector,
            "chat_runs",
        )
        assert "token_hash" in _inspected_unique_constraint_text(
            inspector,
            "login_sessions",
        )
        assert "session_id" in _inspected_unique_constraint_text(inspector, "chats")
        assert "run_id" in _inspected_unique_constraint_text(
            inspector,
            "user_instructions",
        )
        assert "run_id" in _inspected_unique_constraint_text(
            inspector,
            "answer_blocks",
        )
        assert "position" in _inspected_unique_constraint_text(
            inspector,
            "answer_blocks",
        )
        assert "answer_block_id" in _inspected_unique_constraint_text(
            inspector,
            "references",
        )
        assert "position" in _inspected_unique_constraint_text(
            inspector,
            "references",
        )
        assert "storage_path" in _inspected_unique_constraint_text(
            inspector,
            "artifacts",
        )
    finally:
        engine.dispose()


def test_migrations_create_foundation_foreign_keys_checks_and_indexes() -> None:
    """
    観点：DBマイグレーションが物理データ設計の主要制約と索引を作成すること
    確認：FK、CHECK、通常INDEX、UNIQUE、未完了run部分UNIQUEが
    PostgreSQL inspect結果に存在すること
    """
    database_url = foundation_test_database_url()

    prepare_foundation_database(database_url)
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "user_id->users.id" in _inspected_foreign_key_text(
            inspector,
            "login_sessions",
        )
        assert "ondelete=CASCADE" in _inspected_foreign_key_text(
            inspector,
            "login_sessions",
        )
        assert "chat_id->chats.id" in _inspected_foreign_key_text(
            inspector,
            "chat_runs",
        )
        assert "ondelete=CASCADE" in _inspected_foreign_key_text(
            inspector,
            "chat_runs",
        )
        assert "run_id->chat_runs.id" in _inspected_foreign_key_text(
            inspector,
            "answer_blocks",
        )
        assert "ondelete=CASCADE" in _inspected_foreign_key_text(
            inspector,
            "answer_blocks",
        )
        assert "answer_block_id->answer_blocks.id" in _inspected_foreign_key_text(
            inspector,
            "references",
        )
        assert "active" in _inspected_check_constraint_text(inspector, "users")
        assert "deleting" in _inspected_check_constraint_text(inspector, "chats")
        assert "accepted" in _inspected_check_constraint_text(inspector, "chat_runs")
        assert "page_start" in _inspected_check_constraint_text(
            inspector,
            "references",
        )
        assert "page_end" in _inspected_check_constraint_text(inspector, "references")
        assert "user_id" in _inspected_index_text(inspector, "login_sessions")
        assert "expires_at" in _inspected_index_text(inspector, "login_sessions")
        assert "user_id" in _inspected_index_text(inspector, "chats")
        assert "chat_state" in _inspected_index_text(inspector, "chats")
        assert "updated_at DESC" in _postgres_index_definition(
            engine,
            "ix_chats_user_state_updated_at",
        )
        assert "started_at" in _inspected_index_text(inspector, "chat_runs")
        assert "chat_runs_one_unfinished_per_chat" in _inspected_index_text(
            inspector,
            "chat_runs",
        )
        assert "created_at" in _inspected_index_text(
            inspector,
            "intermediate_messages",
        )
    finally:
        engine.dispose()


def test_prepare_database_rejects_non_test_database_before_schema_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    観点：結合テスト支援コードがDB初期化前に接続先の安全性を検証すること
    確認：テスト用DB名、ユーザ、ポートではないURLでは
    DROP SCHEMA相当の初期化処理を呼ばずに失敗すること
    """

    class FakeEngine:
        def dispose(self) -> None:
            return

    @dataclass(slots=True)
    class ResetCallRecorder:
        called: bool = False

    recorder = ResetCallRecorder()

    def fake_create_engine(database_url: str) -> FakeEngine:
        assert database_url
        return FakeEngine()

    def fail_if_schema_reset_runs(engine: Engine) -> None:
        assert engine is not None
        recorder.called = True
        raise AssertionError("非テストDBへスキーマ初期化が実行されました")

    monkeypatch.setattr(foundation, "create_engine", fake_create_engine)
    monkeypatch.setattr(foundation, "_reset_public_schema", fail_if_schema_reset_runs)

    with pytest.raises(RuntimeError, match="結合テスト用DB"):
        foundation.prepare_foundation_database(
            "postgresql+psycopg://d_concierge:d_concierge@127.0.0.1:5432/d_concierge",
        )

    assert not recorder.called


def test_unfinished_chat_run_partial_unique_index_is_enforced() -> None:
    """
    観点：Repository境界の未完了run競合をDB制約で支えること
    確認：同一チャットへaccepted、running、validating、cancel_requestedの未完了runを複数登録すると部分UNIQUE索引で拒否されること
    """
    database_url = foundation_test_database_url()

    prepare_foundation_database(database_url)
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        users = metadata.tables["users"]
        chats = metadata.tables["chats"]
        chat_runs = metadata.tables["chat_runs"]
        now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

        with engine.begin() as connection:
            connection.execute(
                users.insert().values(
                    id="user-001",
                    user_name="テストユーザ",
                    password_hash="hashed-password",
                    user_state="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                chats.insert().values(
                    id=UUID("11111111-1111-7111-8111-111111111111"),
                    user_id="user-001",
                    session_id=UUID("22222222-2222-7222-8222-222222222222"),
                    chat_state="active",
                    title="基盤テスト",
                    generation_conversation_id=None,
                    validation_conversation_id=None,
                    updated_at=now,
                )
            )
            connection.execute(
                chat_runs.insert().values(
                    id=UUID("33333333-3333-7333-8333-333333333333"),
                    chat_id=UUID("11111111-1111-7111-8111-111111111111"),
                    state="accepted",
                    started_at=now,
                    execution_deadline_at=now + timedelta(seconds=120),
                    ended_at=None,
                    user_message=None,
                )
            )

        _assert_integrity_error(
            engine,
            chat_runs.insert().values(
                id=UUID("44444444-4444-7444-8444-444444444444"),
                chat_id=UUID("11111111-1111-7111-8111-111111111111"),
                state="running",
                started_at=now,
                execution_deadline_at=now + timedelta(seconds=120),
                ended_at=None,
                user_message=None,
            ),
        )
    finally:
        engine.dispose()


def test_schema_rejects_invalid_user_state_and_duplicate_session_token() -> None:
    """
    観点：migration適用後のDB制約が不正データを拒否すること
    確認：未定義のuser_stateと重複token_hashがPostgreSQL制約違反として拒否されること
    """
    database_url = foundation_test_database_url()

    prepare_foundation_database(database_url)
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        users = metadata.tables["users"]
        login_sessions = metadata.tables["login_sessions"]
        now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    users.insert().values(
                        id="invalid-state-user",
                        user_name="不正状態",
                        password_hash="hashed-password",
                        user_state="disabled",
                        created_at=now,
                        updated_at=now,
                    )
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    users.insert().values(
                        id="user-unique",
                        user_name="重複検証",
                        password_hash="hashed-password",
                        user_state="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
                connection.execute(
                    login_sessions.insert().values(
                        token_hash="duplicated-token-hash",
                        user_id="user-unique",
                        expires_at=now + timedelta(days=1),
                        created_at=now,
                        updated_at=now,
                    )
                )
                connection.execute(
                    login_sessions.insert().values(
                        token_hash="duplicated-token-hash",
                        user_id="user-unique",
                        expires_at=now + timedelta(days=1),
                        created_at=now,
                        updated_at=now,
                    )
                )
    finally:
        engine.dispose()


def test_schema_rejects_representative_answer_reference_artifact_constraints() -> None:
    """
    観点：migration適用後のDB制約が回答、参照元、成果物の主要不変条件を拒否すること
    確認：回答表示順、参照元表示順、成果物保存先の重複と不正な表示順がPostgreSQL制約違反になること
    """
    database_url = foundation_test_database_url()

    prepare_foundation_database(database_url)
    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        tables = {
            table_name: metadata.tables[table_name]
            for table_name in expected_foundation_table_names()
        }
        now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        _insert_foundation_answer_rows(engine, tables, now)

        _assert_integrity_error(
            engine,
            tables["chats"]
            .insert()
            .values(
                id=UUID("99999999-9999-7999-8999-999999999999"),
                user_id="user-001",
                session_id=UUID("22222222-2222-7222-8222-222222222222"),
                chat_state="active",
                title="重複セッションID",
                generation_conversation_id=None,
                validation_conversation_id=None,
                updated_at=now,
            ),
        )
        _assert_integrity_error(
            engine,
            tables["answer_blocks"]
            .insert()
            .values(
                id=UUID("99999999-9999-7999-8999-999999999998"),
                run_id=UUID("33333333-3333-7333-8333-333333333333"),
                position=1,
                markdown="重複回答表示順",
            ),
        )
        _assert_integrity_error(
            engine,
            tables["answer_blocks"]
            .insert()
            .values(
                id=UUID("99999999-9999-7999-8999-999999999997"),
                run_id=UUID("33333333-3333-7333-8333-333333333333"),
                position=0,
                markdown="不正な回答表示順",
            ),
        )
        _assert_integrity_error(
            engine,
            tables["references"]
            .insert()
            .values(
                id=UUID("99999999-9999-7999-8999-999999999996"),
                answer_block_id=UUID("55555555-5555-7555-8555-555555555555"),
                position=1,
                source_type="pdf",
                label="重複参照元",
                locator=_reference_locator(),
            ),
        )
        _assert_integrity_error(
            engine,
            tables["artifacts"]
            .insert()
            .values(
                id=UUID("99999999-9999-7999-8999-999999999995"),
                answer_block_id=UUID("55555555-5555-7555-8555-555555555555"),
                mime_type="text/plain",
                storage_path="user-001/session/artifact.txt",
                created_at=now,
            ),
        )
    finally:
        engine.dispose()


def _inspected_column_names(inspector: Inspector, table_name: str) -> tuple[str, ...]:
    return tuple(column["name"] for column in inspector.get_columns(table_name))


def _inspected_index_names(inspector: Inspector, table_name: str) -> tuple[str, ...]:
    return tuple(str(index["name"]) for index in inspector.get_indexes(table_name))


def _inspected_unique_constraint_text(
    inspector: Inspector,
    table_name: str,
) -> str:
    constraints = []
    for constraint in inspector.get_unique_constraints(table_name):
        column_names = constraint["column_names"]
        constraints.append(f"{constraint['name']} columns={column_names}")
    return "\n".join(constraints)


def _inspected_foreign_key_text(inspector: Inspector, table_name: str) -> str:
    foreign_keys = []
    for foreign_key in inspector.get_foreign_keys(table_name):
        constrained_columns = foreign_key["constrained_columns"]
        referred_table = foreign_key["referred_table"]
        referred_columns = foreign_key["referred_columns"]
        options = foreign_key["options"]
        foreign_keys.append(
            f"{','.join(str(column) for column in constrained_columns)}->"
            f"{referred_table}.{','.join(str(column) for column in referred_columns)} "
            f"ondelete={options.get('ondelete')}"
        )
    return "\n".join(foreign_keys)


def _inspected_check_constraint_text(inspector: Inspector, table_name: str) -> str:
    constraints = []
    for constraint in inspector.get_check_constraints(table_name):
        constraints.append(f"{constraint['name']} sql={constraint['sqltext']}")
    return "\n".join(constraints)


def _inspected_index_text(inspector: Inspector, table_name: str) -> str:
    indexes = []
    for index in inspector.get_indexes(table_name):
        column_names = index["column_names"]
        indexes.append(
            f"{index['name']} columns={column_names} unique={index['unique']}"
        )
    return "\n".join(indexes)


def _postgres_index_definition(engine: Engine, index_name: str) -> str:
    with engine.connect() as connection:
        result = connection.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' "
                "AND tablename = 'chats' "
                "AND indexname = :index_name"
            ),
            {"index_name": index_name},
        )
        index_definition = result.scalar_one()
    assert isinstance(index_definition, str)
    return index_definition


def _insert_foundation_answer_rows(
    engine: Engine,
    tables: dict[str, Table],
    now: datetime,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            tables["users"]
            .insert()
            .values(
                id="user-001",
                user_name="テストユーザ",
                password_hash="hashed-password",
                user_state="active",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            tables["chats"]
            .insert()
            .values(
                id=UUID("11111111-1111-7111-8111-111111111111"),
                user_id="user-001",
                session_id=UUID("22222222-2222-7222-8222-222222222222"),
                chat_state="active",
                title="基盤テスト",
                generation_conversation_id=None,
                validation_conversation_id=None,
                updated_at=now,
            )
        )
        connection.execute(
            tables["chat_runs"]
            .insert()
            .values(
                id=UUID("33333333-3333-7333-8333-333333333333"),
                chat_id=UUID("11111111-1111-7111-8111-111111111111"),
                state="completed",
                started_at=now,
                execution_deadline_at=now + timedelta(seconds=120),
                ended_at=now + timedelta(seconds=10),
                user_message=None,
            )
        )
        connection.execute(
            tables["answer_blocks"]
            .insert()
            .values(
                id=UUID("55555555-5555-7555-8555-555555555555"),
                run_id=UUID("33333333-3333-7333-8333-333333333333"),
                position=1,
                markdown="回答本文",
            )
        )
        connection.execute(
            tables["references"]
            .insert()
            .values(
                id=UUID("66666666-6666-7666-8666-666666666666"),
                answer_block_id=UUID("55555555-5555-7555-8555-555555555555"),
                position=1,
                source_type="pdf",
                label="参照元",
                locator=_reference_locator(),
            )
        )
        connection.execute(
            tables["artifacts"]
            .insert()
            .values(
                id=UUID("77777777-7777-7777-8777-777777777777"),
                answer_block_id=UUID("55555555-5555-7555-8555-555555555555"),
                mime_type="text/plain",
                storage_path="user-001/session/artifact.txt",
                created_at=now,
            )
        )


def _reference_locator() -> ReferenceLocatorPayload:
    return {
        "path": "docs/source.pdf",
        "page_start": 1,
        "page_end": 1,
    }


def _assert_integrity_error(engine: Engine, statement: Insert) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(statement)

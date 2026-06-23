from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    MetaData,
    Table,
    UniqueConstraint,
)

from backend.tests.support.foundation import expected_foundation_table_names


def test_orm_model_modules_define_required_table_classes() -> None:
    """
    観点：物理データ設計で指定されたORMモデル配置を満たすこと
    確認：base.py、user.py、chat.py、answer.pyからBaseと主要ORMモデルを読み込め、
    対応テーブル名が設計どおりであること
    """
    from backend.infrastructure.database.models import answer, chat, user
    from backend.infrastructure.database.models.base import Base

    assert Base.metadata is not None
    assert user.UserModel.__tablename__ == "users"
    assert user.LoginSessionModel.__tablename__ == "login_sessions"
    assert chat.ChatModel.__tablename__ == "chats"
    assert chat.ChatRunModel.__tablename__ == "chat_runs"
    assert answer.AnswerBlockModel.__tablename__ == "answer_blocks"
    assert answer.ReferenceModel.__tablename__ == "references"
    assert answer.ArtifactModel.__tablename__ == "artifacts"


def test_metadata_contains_all_foundation_tables_and_columns() -> None:
    """
    観点：DBモデルがF001で必要な基盤テーブルを定義すること
    確認：users、login_sessions、chats、chat_runs、user_instructions、
    intermediate_messages、answer_blocks、references、artifactsの列が物理設計どおりであること
    """
    metadata = _load_foundation_metadata()

    assert tuple(sorted(metadata.tables.keys())) == tuple(
        sorted(expected_foundation_table_names())
    )
    assert _column_names(metadata.tables["users"]) == (
        "id",
        "user_name",
        "password_hash",
        "user_state",
        "created_at",
        "updated_at",
    )
    assert _column_names(metadata.tables["login_sessions"]) == (
        "id",
        "token_hash",
        "user_id",
        "expires_at",
        "created_at",
        "updated_at",
    )
    assert _column_names(metadata.tables["chats"]) == (
        "id",
        "user_id",
        "session_id",
        "chat_state",
        "title",
        "generation_conversation_id",
        "validation_conversation_id",
        "updated_at",
    )
    assert _column_names(metadata.tables["chat_runs"]) == (
        "id",
        "chat_id",
        "state",
        "started_at",
        "execution_deadline_at",
        "ended_at",
        "user_message",
    )
    assert _column_names(metadata.tables["user_instructions"]) == (
        "id",
        "run_id",
        "body",
    )
    assert _column_names(metadata.tables["intermediate_messages"]) == (
        "id",
        "run_id",
        "body",
        "created_at",
    )
    assert _column_names(metadata.tables["answer_blocks"]) == (
        "id",
        "run_id",
        "position",
        "markdown",
    )
    assert _column_names(metadata.tables["references"]) == (
        "id",
        "answer_block_id",
        "position",
        "source_type",
        "label",
        "locator",
    )
    assert _column_names(metadata.tables["artifacts"]) == (
        "id",
        "answer_block_id",
        "mime_type",
        "storage_path",
        "created_at",
    )


def test_metadata_defines_state_and_locator_constraints() -> None:
    """
    観点：DBモデルが固定状態・参照元locatorの不変条件をDB制約として持つこと
    確認：ユーザ状態、チャット状態、run状態、PDF参照元、ページ範囲、空白指示のCHECK制約がmetadata上に定義されること
    """
    metadata = _load_foundation_metadata()

    users_constraints = _check_constraint_text(metadata.tables["users"])
    chats_constraints = _check_constraint_text(metadata.tables["chats"])
    chat_runs_constraints = _check_constraint_text(metadata.tables["chat_runs"])
    instructions_constraints = _check_constraint_text(
        metadata.tables["user_instructions"]
    )
    references_constraints = _check_constraint_text(metadata.tables["references"])

    assert "active" in users_constraints
    assert "deleting" in users_constraints
    assert "active" in chats_constraints
    assert "deleting" in chats_constraints
    for state in (
        "accepted",
        "running",
        "validating",
        "cancel_requested",
        "canceled",
        "completed",
        "error",
        "timed_out",
    ):
        assert state in chat_runs_constraints
    assert "trim" in instructions_constraints
    assert "source_type" in references_constraints
    assert "pdf" in references_constraints
    assert "page_start" in references_constraints
    assert "page_end" in references_constraints


def test_metadata_defines_column_types_nullability_and_defaults() -> None:
    """
    観点：DBモデルが物理データ設計の列型、NULL可否、DEFAULTをmetadataへ反映すること
    確認：主要ID、状態、日時、JSONB、表示順、保存先参照の型とNULL可否、状態列のDEFAULTが設計どおりであること
    """
    metadata = _load_foundation_metadata()

    assert "type=VARCHAR(30)" in _column_contract(metadata.tables["users"], "id")
    assert "nullable=False" in _column_contract(metadata.tables["users"], "id")
    assert "primary_key=True" in _column_contract(metadata.tables["users"], "id")
    assert "type=VARCHAR(30)" in _column_contract(
        metadata.tables["users"],
        "user_name",
    )
    assert "type=TEXT" in _column_contract(metadata.tables["users"], "password_hash")
    assert "type=VARCHAR(20)" in _column_contract(
        metadata.tables["users"],
        "user_state",
    )
    assert "active" in _column_contract(metadata.tables["users"], "user_state")
    assert "timezone=True" in _column_contract(metadata.tables["users"], "created_at")
    assert "type=BIGINT" in _column_contract(metadata.tables["login_sessions"], "id")
    assert "type=UUID" in _column_contract(metadata.tables["chats"], "id")
    assert "type=VARCHAR(50)" in _column_contract(metadata.tables["chats"], "title")
    assert "active" in _column_contract(metadata.tables["chats"], "chat_state")
    assert "nullable=True" in _column_contract(
        metadata.tables["chats"],
        "generation_conversation_id",
    )
    assert "nullable=True" in _column_contract(
        metadata.tables["chat_runs"],
        "execution_deadline_at",
    )
    assert "type=INTEGER" in _column_contract(
        metadata.tables["answer_blocks"],
        "position",
    )
    assert "type=JSONB" in _column_contract(metadata.tables["references"], "locator")
    assert "type=VARCHAR(100)" in _column_contract(
        metadata.tables["artifacts"],
        "mime_type",
    )
    assert "type=TEXT" in _column_contract(metadata.tables["artifacts"], "storage_path")


def test_metadata_defines_primary_keys_foreign_keys_and_unique_constraints() -> None:
    """
    観点：DBモデルがPK、FK、UNIQUE、cascade削除用FKをmetadataへ反映すること
    確認：全テーブルの主キー、関連テーブルへのFK、token_hash/session_id/表示順/storage_pathの一意制約が設計どおりであること
    """
    metadata = _load_foundation_metadata()

    for table_name in expected_foundation_table_names():
        assert _primary_key_columns(metadata.tables[table_name]) in (
            ("id",),
            ("id", "run_id"),
        )

    assert "user_id->users.id ondelete=CASCADE" in _foreign_key_contracts(
        metadata.tables["login_sessions"]
    )
    assert "user_id->users.id ondelete=CASCADE" in _foreign_key_contracts(
        metadata.tables["chats"]
    )
    assert "chat_id->chats.id ondelete=CASCADE" in _foreign_key_contracts(
        metadata.tables["chat_runs"]
    )
    assert "run_id->chat_runs.id ondelete=CASCADE" in _foreign_key_contracts(
        metadata.tables["user_instructions"]
    )
    assert "run_id->chat_runs.id ondelete=CASCADE" in _foreign_key_contracts(
        metadata.tables["intermediate_messages"]
    )
    assert "run_id->chat_runs.id ondelete=CASCADE" in _foreign_key_contracts(
        metadata.tables["answer_blocks"]
    )
    assert "answer_block_id->answer_blocks.id ondelete=CASCADE" in (
        _foreign_key_contracts(metadata.tables["references"])
    )
    assert "answer_block_id->answer_blocks.id ondelete=CASCADE" in (
        _foreign_key_contracts(metadata.tables["artifacts"])
    )

    assert _has_unique_columns(metadata.tables["login_sessions"], ("token_hash",))
    assert _has_unique_columns(metadata.tables["chats"], ("session_id",))
    assert _has_unique_columns(metadata.tables["user_instructions"], ("run_id",))
    assert _has_unique_columns(metadata.tables["answer_blocks"], ("run_id", "position"))
    assert _has_unique_columns(
        metadata.tables["references"],
        ("answer_block_id", "position"),
    )
    assert _has_unique_columns(metadata.tables["artifacts"], ("storage_path",))


def test_metadata_defines_all_repository_indexes() -> None:
    """
    観点：DBモデルが履歴取得と未完了run競合防止に必要な索引を定義すること
    確認：期限切れセッション削除、履歴一覧、run検索、中間メッセージ取得、未完了run部分UNIQUE索引がmetadata上に定義されること
    """
    metadata = _load_foundation_metadata()

    login_session_indexes = _index_texts(metadata.tables["login_sessions"])
    chats_indexes = _index_texts(metadata.tables["chats"])
    chat_runs_indexes = _index_texts(metadata.tables["chat_runs"])
    intermediate_message_indexes = _index_texts(
        metadata.tables["intermediate_messages"]
    )

    assert "user_id" in login_session_indexes
    assert "expires_at" in login_session_indexes
    assert "user_id" in chats_indexes
    assert "chat_state" in chats_indexes
    assert "updated_at DESC" in chats_indexes
    assert "chat_id" in chat_runs_indexes
    assert "started_at" in chat_runs_indexes
    assert "id" in chat_runs_indexes
    assert "state" in chat_runs_indexes
    assert "run_id" in intermediate_message_indexes
    assert "created_at" in intermediate_message_indexes
    assert "chat_runs_one_unfinished_per_chat" in chat_runs_indexes
    assert "accepted" in chat_runs_indexes
    assert "running" in chat_runs_indexes
    assert "validating" in chat_runs_indexes
    assert "cancel_requested" in chat_runs_indexes


def _load_foundation_metadata() -> MetaData:
    from backend.infrastructure.database.models import answer, chat, user
    from backend.infrastructure.database.models.base import Base

    assert user.UserModel.__tablename__ == "users"
    assert chat.ChatModel.__tablename__ == "chats"
    assert answer.AnswerBlockModel.__tablename__ == "answer_blocks"
    return Base.metadata


def _column_names(table: Table) -> tuple[str, ...]:
    return tuple(column.name for column in table.columns)


def _column_contract(table: Table, column_name: str) -> str:
    column = table.columns[column_name]
    timezone = getattr(column.type, "timezone", None)
    return (
        f"type={column.type} nullable={column.nullable} "
        f"primary_key={column.primary_key} unique={column.unique} "
        f"default={column.default} server_default={column.server_default} "
        f"timezone={timezone}"
    )


def _check_constraint_text(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _index_texts(table: Table) -> str:
    index_texts = []
    for index in table.indexes:
        expressions = ", ".join(str(expression) for expression in index.expressions)
        postgresql_where = index.dialect_options["postgresql"].get("where")
        index_texts.append(
            f"{index.name} unique={index.unique} expressions={expressions} "
            f"where={postgresql_where}"
        )
    return "\n".join(index_texts)


def _primary_key_columns(table: Table) -> tuple[str, ...]:
    return tuple(column.name for column in table.primary_key.columns)


def _foreign_key_contracts(table: Table) -> tuple[str, ...]:
    contracts = []
    for constraint in table.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for element in constraint.elements:
                contracts.append(
                    f"{element.parent.name}->{element.target_fullname} "
                    f"ondelete={element.ondelete}"
                )
    return tuple(sorted(contracts))


def _has_unique_columns(table: Table, column_names: tuple[str, ...]) -> bool:
    for column in table.columns:
        if column.unique and (column.name,) == column_names:
            return True
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            constrained_columns = tuple(column.name for column in constraint.columns)
            if constrained_columns == column_names:
                return True
    return False

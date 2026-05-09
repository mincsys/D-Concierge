"""初期スキーマを作成する。

Revision ID: 0001
Revises:
Create Date: 2026-05-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATE_CHECK = (
    "state IN ('受付','実行中','検証中','キャンセル要求中',"
    "'キャンセル済み','完了','エラー','タイムアウト')"
)


def upgrade() -> None:
    op.create_table(
        "local_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    op.create_table(
        "chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("local_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=50), nullable=False),
        sa.Column("generation_conversation_id", sa.String(length=255), nullable=True),
        sa.Column("validation_conversation_id", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["local_user_id"], ["local_users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("session_id", name="uq_chats_session_id"),
    )
    op.create_index(
        "ix_chats_local_user_id_updated_at",
        "chats",
        ["local_user_id", sa.text("updated_at DESC")],
    )

    op.create_table(
        "chat_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_message", sa.Text(), nullable=True),
        sa.CheckConstraint(RUN_STATE_CHECK, name="ck_chat_runs_state"),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_chat_runs_chat_id_started_at_id",
        "chat_runs",
        ["chat_id", "started_at", "id"],
    )
    op.create_index("ix_chat_runs_chat_id_state", "chat_runs", ["chat_id", "state"])
    op.create_index(
        "chat_runs_one_unfinished_per_chat",
        "chat_runs",
        ["chat_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('受付','実行中','検証中','キャンセル要求中')"
        ),
    )

    op.create_table(
        "user_instructions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(body)) > 0", name="ck_user_instructions_body_not_blank"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["chat_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", name="uq_user_instructions_run_id"),
    )

    op.create_table(
        "intermediate_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["chat_runs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_intermediate_messages_run_id_created_at_id",
        "intermediate_messages",
        ["run_id", "created_at", "id"],
    )

    op.create_table(
        "answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["chat_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", name="uq_answers_run_id"),
    )

    op.create_table(
        "references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("locator", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("source_type = 'pdf'", name="ck_references_source_type_pdf"),
        sa.CheckConstraint(
            "jsonb_typeof(locator) = 'object' "
            "AND jsonb_typeof(locator -> 'path') = 'string' "
            "AND jsonb_typeof(locator -> 'page_start') = 'number' "
            "AND jsonb_typeof(locator -> 'page_end') = 'number' "
            "AND (locator ->> 'page_start')::integer > 0 "
            "AND (locator ->> 'page_end')::integer > 0 "
            "AND (locator ->> 'page_start')::integer "
            "<= (locator ->> 'page_end')::integer",
            name="ck_references_locator_pdf",
        ),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("storage_path", name="uq_artifacts_storage_path"),
    )


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("references")
    op.drop_table("answers")
    op.drop_index(
        "ix_intermediate_messages_run_id_created_at_id",
        table_name="intermediate_messages",
    )
    op.drop_table("intermediate_messages")
    op.drop_table("user_instructions")
    op.drop_index("chat_runs_one_unfinished_per_chat", table_name="chat_runs")
    op.drop_index("ix_chat_runs_chat_id_state", table_name="chat_runs")
    op.drop_index("ix_chat_runs_chat_id_started_at_id", table_name="chat_runs")
    op.drop_table("chat_runs")
    op.drop_index("ix_chats_local_user_id_updated_at", table_name="chats")
    op.drop_table("chats")
    op.drop_table("local_users")

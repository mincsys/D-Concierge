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
    "state IN ('accepted','running','validating','cancel_requested',"
    "'canceled','completed','error','timed_out')"
)
CHAT_STATE_CHECK = "chat_state IN ('active','deleting')"
USER_STATE_CHECK = "user_state IN ('active','deleting')"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=30), primary_key=True),
        sa.Column("user_name", sa.String(length=30), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "user_state",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(USER_STATE_CHECK, name="ck_users_user_state"),
    )
    op.create_table(
        "login_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_login_sessions_token_hash"),
    )
    op.create_index(
        "ix_login_sessions_user_id_expires_at",
        "login_sessions",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "ix_login_sessions_expires_at",
        "login_sessions",
        ["expires_at"],
    )

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
        sa.Column("user_id", sa.String(length=30), nullable=True),
        sa.Column("local_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=50), nullable=False),
        sa.Column(
            "chat_state",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("generation_conversation_id", sa.String(length=255), nullable=True),
        sa.Column("validation_conversation_id", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["local_user_id"], ["local_users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(CHAT_STATE_CHECK, name="ck_chats_chat_state"),
        sa.UniqueConstraint("session_id", name="uq_chats_session_id"),
    )
    op.create_index(
        "ix_chats_user_id_updated_at",
        "chats",
        ["user_id", sa.text("updated_at DESC")],
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
            "state IN ('accepted','running','validating','cancel_requested')"
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
        "answer_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.CheckConstraint("position > 0", name="ck_answer_blocks_position_positive"),
        sa.CheckConstraint(
            "length(trim(markdown)) > 0", name="ck_answer_blocks_markdown_not_blank"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["chat_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "run_id", "position", name="uq_answer_blocks_run_id_position"
        ),
    )

    op.create_table(
        "references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("answer_block_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("locator", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("position > 0", name="ck_references_position_positive"),
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
        sa.ForeignKeyConstraint(
            ["answer_block_id"], ["answer_blocks.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "answer_block_id", "position", name="uq_references_block_id_position"
        ),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("answer_block_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["answer_block_id"], ["answer_blocks.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("storage_path", name="uq_artifacts_storage_path"),
    )


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("references")
    op.drop_table("answer_blocks")
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
    op.drop_index("ix_chats_user_id_updated_at", table_name="chats")
    op.drop_table("chats")
    op.drop_table("local_users")
    op.drop_index("ix_login_sessions_expires_at", table_name="login_sessions")
    op.drop_index("ix_login_sessions_user_id_expires_at", table_name="login_sessions")
    op.drop_table("login_sessions")
    op.drop_table("users")

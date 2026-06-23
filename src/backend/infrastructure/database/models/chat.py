from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.models.base import Base


class ChatModel(Base):
    """一連の指示応答をまとめるチャットORMモデル。"""

    __tablename__ = "chats"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_chats_session_id"),
        CheckConstraint(
            "chat_state IN ('active', 'deleting')",
            name="ck_chats_chat_state",
        ),
        Index(
            "ix_chats_user_state_updated_at",
            "user_id",
            "chat_state",
            text("updated_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), nullable=False)
    chat_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
    )
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    generation_conversation_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    validation_conversation_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ChatRunModel(Base):
    """ユーザ指示1回ごとの実行状態ORMモデル。"""

    __tablename__ = "chat_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ("
            "'accepted', 'running', 'validating', 'cancel_requested', "
            "'canceled', 'completed', 'error', 'timed_out'"
            ")",
            name="ck_chat_runs_state",
        ),
        Index("ix_chat_runs_chat_started_id", "chat_id", "started_at", "id"),
        Index("ix_chat_runs_chat_state", "chat_id", "state"),
        Index(
            "chat_runs_one_unfinished_per_chat",
            "chat_id",
            unique=True,
            postgresql_where=text(
                "state IN ('accepted', 'running', 'validating', 'cancel_requested')",
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True)
    chat_id: Mapped[UUID] = mapped_column(
        PgUuid(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    execution_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserInstructionModel(Base):
    """runに対応する利用者指示本文ORMモデル。"""

    __tablename__ = "user_instructions"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_user_instructions_run_id"),
        CheckConstraint("length(trim(body)) > 0", name="ck_user_instructions_body"),
    )

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PgUuid(as_uuid=True),
        ForeignKey("chat_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class IntermediateMessageModel(Base):
    """履歴再表示用の中間メッセージORMモデル。"""

    __tablename__ = "intermediate_messages"
    __table_args__ = (
        Index("ix_intermediate_messages_run_created_id", "run_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PgUuid(as_uuid=True),
        ForeignKey("chat_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

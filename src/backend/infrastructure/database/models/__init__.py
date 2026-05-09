from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.domain.execution.run_state_policy import RunState


class Base(DeclarativeBase):
    """SQLAlchemy ORMモデルの基底。"""


class LocalUserModel(Base):
    """`local_users` テーブルのORMモデル。"""

    __tablename__ = "local_users"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)


class ChatModel(Base):
    """`chats` テーブルのORMモデル。"""

    __tablename__ = "chats"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    local_user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("local_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=False,
        unique=True,
    )
    title: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    generation_conversation_id: Mapped[str | None] = mapped_column(sa.String(255))
    validation_conversation_id: Mapped[str | None] = mapped_column(sa.String(255))
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class ChatRunModel(Base):
    """`chat_runs` テーブルのORMモデル。"""

    __tablename__ = "chat_runs"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    chat_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state: Mapped[RunState] = mapped_column(sa.String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    execution_deadline_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True)
    )
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    user_message: Mapped[str | None] = mapped_column(sa.Text)


class UserInstructionModel(Base):
    """`user_instructions` テーブルのORMモデル。"""

    __tablename__ = "user_instructions"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("chat_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)


class IntermediateMessageModel(Base):
    """`intermediate_messages` テーブルのORMモデル。"""

    __tablename__ = "intermediate_messages"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("chat_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )


class AnswerModel(Base):
    """`answers` テーブルのORMモデル。"""

    __tablename__ = "answers"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("chat_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )


class AnswerBlockModel(Base):
    """`answer_blocks` テーブルのORMモデル。"""

    __tablename__ = "answer_blocks"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    answer_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    markdown: Mapped[str] = mapped_column(sa.Text, nullable=False)


class ReferenceModel(Base):
    """`references` テーブルのORMモデル。"""

    __tablename__ = "references"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    answer_block_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("answer_blocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    locator: Mapped[dict[str, str | int]] = mapped_column(sa.JSON, nullable=False)


class ArtifactModel(Base):
    """`artifacts` テーブルのORMモデル。"""

    __tablename__ = "artifacts"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    answer_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )

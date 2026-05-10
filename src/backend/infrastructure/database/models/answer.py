from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.models.base import Base


class AnswerBlockModel(Base):
    """`answer_blocks` テーブルのORMモデル。"""

    __tablename__ = "answer_blocks"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("chat_runs.id", ondelete="CASCADE"),
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
    answer_block_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("answer_blocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )

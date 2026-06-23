from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.models.base import Base


class AnswerBlockModel(Base):
    """完了runに紐づく回答ブロックORMモデル。"""

    __tablename__ = "answer_blocks"
    __table_args__ = (
        UniqueConstraint("run_id", "position", name="uq_answer_blocks_run_position"),
        CheckConstraint("position > 0", name="ck_answer_blocks_position_positive"),
    )

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PgUuid(as_uuid=True),
        ForeignKey("chat_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)


class ReferenceModel(Base):
    """PDF参照元メタ情報ORMモデル。"""

    __tablename__ = "references"
    __table_args__ = (
        UniqueConstraint(
            "answer_block_id",
            "position",
            name="uq_references_answer_block_position",
        ),
        CheckConstraint("position > 0", name="ck_references_position_positive"),
        CheckConstraint("source_type = 'pdf'", name="ck_references_source_type_pdf"),
        CheckConstraint(
            "jsonb_typeof(locator -> 'path') = 'string' "
            "AND jsonb_typeof(locator -> 'page_start') = 'number' "
            "AND jsonb_typeof(locator -> 'page_end') = 'number' "
            "AND (locator ->> 'page_start')::integer > 0 "
            "AND (locator ->> 'page_end')::integer >= "
            "(locator ->> 'page_start')::integer",
            name="ck_references_locator_page_range",
        ),
        Index("ix_references_answer_block_position", "answer_block_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True)
    answer_block_id: Mapped[UUID] = mapped_column(
        PgUuid(as_uuid=True),
        ForeignKey("answer_blocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    locator: Mapped[dict[str, str | int]] = mapped_column(JSONB, nullable=False)


class ArtifactModel(Base):
    """保存済みCodex成果物メタ情報ORMモデル。"""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("storage_path", name="uq_artifacts_storage_path"),
        Index("ix_artifacts_answer_block_id", "answer_block_id"),
    )

    id: Mapped[UUID] = mapped_column(PgUuid(as_uuid=True), primary_key=True)
    answer_block_id: Mapped[UUID] = mapped_column(
        PgUuid(as_uuid=True),
        ForeignKey("answer_blocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

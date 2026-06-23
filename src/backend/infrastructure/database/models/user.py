from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.models.base import Base


class UserModel(Base):
    """ログインユーザを保持するORMモデル。"""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "id ~ '^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,28}[A-Za-z0-9])?$'",
            name="ck_users_id_format",
        ),
        CheckConstraint(
            "user_state IN ('active', 'deleting')",
            name="ck_users_user_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(30), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    user_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class LoginSessionModel(Base):
    """ブラウザごとのログインセッションを保持するORMモデル。"""

    __tablename__ = "login_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_login_sessions_token_hash"),
        Index("ix_login_sessions_user_id_expires_at", "user_id", "expires_at"),
        Index("ix_login_sessions_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

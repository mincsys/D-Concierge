from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from backend.tests.support.foundation import (
    foundation_test_database_url,
    prepare_foundation_database,
)

NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def test_login_session_schema_stores_hash_and_rejects_duplicate_tokens() -> None:
    """
    観点：login_sessionsがCookie生トークンではなく照合用ハッシュを保存する契約であること
    確認：token_hashの一意制約により同一セッションハッシュの重複登録を拒否し、
    保存値が生Cookieトークンと一致しないこと
    """
    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    engine = create_engine(database_url)
    try:
        _insert_user(engine, user_id="user-001")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO login_sessions
                      (token_hash, user_id, expires_at, created_at, updated_at)
                    VALUES
                      (:token_hash, :user_id, :expires_at, :created_at, :updated_at)
                    """,
                ),
                {
                    "token_hash": "sha256:first-cookie-token",
                    "user_id": "user-001",
                    "expires_at": NOW + timedelta(days=400),
                    "created_at": NOW,
                    "updated_at": NOW,
                },
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO login_sessions
                          (token_hash, user_id, expires_at, created_at, updated_at)
                        VALUES
                          (:token_hash, :user_id, :expires_at, :created_at, :updated_at)
                        """,
                    ),
                    {
                        "token_hash": "sha256:first-cookie-token",
                        "user_id": "user-001",
                        "expires_at": NOW + timedelta(days=400),
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                )

        with engine.connect() as connection:
            stored_hash = connection.execute(
                text(
                    """
                    SELECT token_hash
                    FROM login_sessions
                    WHERE user_id = :user_id
                    """,
                ),
                {"user_id": "user-001"},
            ).scalar_one()

        assert stored_hash == "sha256:first-cookie-token"
        assert stored_hash != "first-cookie-token"
    finally:
        engine.dispose()


def test_account_delete_acceptance_schema_supports_state_transition() -> None:
    """
    観点：アカウント削除受付時のDB状態遷移をF001スキーマが支えられること
    確認：ユーザとチャットをdeletingへ更新し、対象ユーザの全login_sessionsを削除しても
    外部キーと制約に反しないこと
    """
    database_url = foundation_test_database_url()
    prepare_foundation_database(database_url)
    engine = create_engine(database_url)
    first_chat_id = UUID("018fe2d4-0000-7000-8000-000000000101")
    second_chat_id = UUID("018fe2d4-0000-7000-8000-000000000102")
    try:
        _insert_user(engine, user_id="user-001")
        with engine.begin() as connection:
            for token_hash in ("sha256:first-token", "sha256:second-token"):
                connection.execute(
                    text(
                        """
                        INSERT INTO login_sessions
                          (token_hash, user_id, expires_at, created_at, updated_at)
                        VALUES
                          (:token_hash, :user_id, :expires_at, :created_at, :updated_at)
                        """,
                    ),
                    {
                        "token_hash": token_hash,
                        "user_id": "user-001",
                        "expires_at": NOW + timedelta(days=400),
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                )
            for chat_id in (first_chat_id, second_chat_id):
                connection.execute(
                    text(
                        """
                        INSERT INTO chats
                          (id, user_id, session_id, chat_state, title, updated_at)
                        VALUES
                          (:id, :user_id, :session_id, :chat_state, :title, :updated_at)
                        """,
                    ),
                    {
                        "id": chat_id,
                        "user_id": "user-001",
                        "session_id": chat_id,
                        "chat_state": "active",
                        "title": "削除受付確認",
                        "updated_at": NOW,
                    },
                )

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE users
                    SET user_state = 'deleting', updated_at = :updated_at
                    WHERE id = :user_id
                    """,
                ),
                {"user_id": "user-001", "updated_at": NOW},
            )
            connection.execute(
                text(
                    """
                    UPDATE chats
                    SET chat_state = 'deleting', updated_at = :updated_at
                    WHERE user_id = :user_id
                    """,
                ),
                {"user_id": "user-001", "updated_at": NOW},
            )
            connection.execute(
                text(
                    """
                    DELETE FROM login_sessions
                    WHERE user_id = :user_id
                    """,
                ),
                {"user_id": "user-001"},
            )

        with engine.connect() as connection:
            user_state = connection.execute(
                text("SELECT user_state FROM users WHERE id = :user_id"),
                {"user_id": "user-001"},
            ).scalar_one()
            deleting_chat_count = connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM chats
                    WHERE user_id = :user_id AND chat_state = 'deleting'
                    """,
                ),
                {"user_id": "user-001"},
            ).scalar_one()
            session_count = connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM login_sessions
                    WHERE user_id = :user_id
                    """,
                ),
                {"user_id": "user-001"},
            ).scalar_one()

        assert user_state == "deleting"
        assert deleting_chat_count == 2
        assert session_count == 0
    finally:
        engine.dispose()


def _insert_user(engine: Engine, *, user_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users
                  (id, user_name, password_hash, user_state, created_at, updated_at)
                VALUES
                  (:id, :user_name, :password_hash, :user_state,
                   :created_at, :updated_at)
                """,
            ),
            {
                "id": user_id,
                "user_name": "利用者",
                "password_hash": "hashed-password",
                "user_state": "active",
                "created_at": NOW,
                "updated_at": NOW,
            },
        )

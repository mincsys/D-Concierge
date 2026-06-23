from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.application.ports.database.dto import (
    AccountDeletionTarget,
    AccountUserData,
    LoginSessionData,
)
from backend.domain.execution.run_state import RunState
from backend.infrastructure.database.models.chat import ChatModel, ChatRunModel
from backend.infrastructure.database.models.user import (
    LoginSessionModel,
    UserModel,
)


@dataclass(slots=True)
class SqlAlchemyAccountRepository:
    """アカウント関連RepositoryのSQLAlchemy実装。"""

    session: Session

    def create_user(
        self,
        user_id: str,
        user_name: str,
        password_hash: str,
        created_at: datetime,
    ) -> AccountUserData:
        user = UserModel(
            id=user_id,
            user_name=user_name,
            password_hash=password_hash,
            user_state="active",
            created_at=created_at,
            updated_at=created_at,
        )
        self.session.add(user)
        self.session.flush()
        return _account_user_data(user)

    def get_user_for_login(self, user_id: str) -> AccountUserData | None:
        user = self.session.get(UserModel, user_id)
        if user is None:
            return None
        return _account_user_data(user)

    def update_user_name(
        self,
        user_id: str,
        user_name: str,
        updated_at: datetime,
    ) -> AccountUserData | None:
        user = self.session.get(UserModel, user_id)
        if user is None or user.user_state != "active":
            return None
        user.user_name = user_name
        user.updated_at = updated_at
        self.session.flush()
        return _account_user_data(user)

    def update_password_hash(
        self,
        user_id: str,
        password_hash: str,
        updated_at: datetime,
    ) -> None:
        user = self.session.get(UserModel, user_id)
        if user is None or user.user_state != "active":
            return
        user.password_hash = password_hash
        user.updated_at = updated_at
        self.session.flush()

    def create_login_session(
        self,
        token_hash: str,
        user_id: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> LoginSessionData:
        session = LoginSessionModel(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            created_at=created_at,
            updated_at=created_at,
        )
        self.session.add(session)
        self.session.flush()
        found = self.find_session_by_token_hash(token_hash)
        if found is None:
            raise RuntimeError("作成したログインセッションを取得できません。")
        return found

    def find_session_by_token_hash(
        self,
        token_hash: str,
    ) -> LoginSessionData | None:
        statement = (
            select(LoginSessionModel, UserModel)
            .join(UserModel, LoginSessionModel.user_id == UserModel.id)
            .where(LoginSessionModel.token_hash == token_hash)
        )
        row = self.session.execute(statement).first()
        if row is None:
            return None
        login_session, user = row
        return _login_session_data(login_session, user)

    def delete_session_by_token_hash(self, token_hash: str) -> int:
        login_session = self.session.execute(
            select(LoginSessionModel).where(LoginSessionModel.token_hash == token_hash)
        ).scalar_one_or_none()
        if login_session is None:
            return 0
        self.session.delete(login_session)
        self.session.flush()
        return 1

    def delete_sessions_by_user_id(self, user_id: str) -> int:
        login_sessions = tuple(
            self.session.execute(
                select(LoginSessionModel).where(LoginSessionModel.user_id == user_id)
            ).scalars()
        )
        for login_session in login_sessions:
            self.session.delete(login_session)
        self.session.flush()
        return len(login_sessions)

    def mark_user_deleting(
        self,
        user_id: str,
        updated_at: datetime,
    ) -> str | None:
        user = self.session.get(UserModel, user_id)
        if user is None:
            return None
        user.user_state = "deleting"
        user.updated_at = updated_at
        self.session.flush()
        return "deleting"

    def mark_user_chats_deleting(self, user_id: str, updated_at: datetime) -> int:
        chats = tuple(
            self.session.execute(
                select(ChatModel).where(ChatModel.user_id == user_id)
            ).scalars()
        )
        for chat in chats:
            chat.chat_state = "deleting"
            chat.updated_at = updated_at
        self.session.flush()
        return len(chats)

    def find_user_by_id(self, user_id: str) -> AccountUserData | None:
        return self.get_user_for_login(user_id)

    def find_user_by_name(self, user_name: str) -> AccountUserData | None:
        user = self.session.execute(
            select(UserModel).where(UserModel.user_name == user_name)
        ).scalar_one_or_none()
        if user is None:
            return None
        return _account_user_data(user)

    def find_valid_session(self, token_hash: str) -> LoginSessionData | None:
        return self.find_session_by_token_hash(token_hash)

    def delete_session(self, token_hash: str) -> None:
        self.delete_session_by_token_hash(token_hash)

    def save_user(self, user: AccountUserData) -> None:
        existing = self.session.get(UserModel, user.user_id)
        if existing is None:
            return
        existing.user_name = user.user_name
        existing.password_hash = user.password_hash
        existing.user_state = user.user_state
        existing.updated_at = user.updated_at
        self.session.flush()

    def delete_user(self, user_id: str) -> None:
        user = self.session.get(UserModel, user_id)
        if user is not None:
            self.session.delete(user)
            self.session.flush()

    def get_account_deletion_target(
        self,
        user_id: str,
    ) -> AccountDeletionTarget | None:
        user = self.session.get(UserModel, user_id)
        if user is None or user.user_state != "deleting":
            return None
        active_chat_session_ids = tuple(
            self.session.execute(
                select(ChatModel.session_id)
                .where(ChatModel.user_id == user_id)
                .order_by(ChatModel.updated_at, ChatModel.id)
            ).scalars()
        )
        unfinished_run_ids = tuple(
            self.session.execute(
                select(ChatRunModel.id)
                .join(ChatModel, ChatModel.id == ChatRunModel.chat_id)
                .where(
                    ChatModel.user_id == user_id,
                    ChatRunModel.state.in_(
                        (
                            RunState.ACCEPTED.value,
                            RunState.RUNNING.value,
                            RunState.VALIDATING.value,
                            RunState.CANCEL_REQUESTED.value,
                        )
                    ),
                )
                .order_by(ChatRunModel.started_at, ChatRunModel.id)
            ).scalars()
        )
        return AccountDeletionTarget(
            user_id=user.id,
            active_chat_session_ids=active_chat_session_ids,
            unfinished_run_ids=unfinished_run_ids,
        )

    def delete_account_data(self, user_id: str) -> None:
        user = self.session.get(UserModel, user_id)
        if user is None:
            return
        try:
            self.session.delete(user)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def delete_expired_sessions(self, now: datetime) -> int:
        login_sessions = tuple(
            self.session.execute(
                select(LoginSessionModel).where(LoginSessionModel.expires_at <= now)
            ).scalars()
        )
        for login_session in login_sessions:
            self.session.delete(login_session)
        self.session.flush()
        return len(login_sessions)

    def list_deleting_user_ids(self) -> tuple[str, ...]:
        return tuple(
            self.session.execute(
                select(UserModel.id)
                .where(UserModel.user_state == "deleting")
                .order_by(UserModel.updated_at, UserModel.id)
            ).scalars()
        )


def _account_user_data(user: UserModel) -> AccountUserData:
    return AccountUserData(
        user_id=user.id,
        user_name=user.user_name,
        password_hash=user.password_hash,
        user_state=user.user_state,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _login_session_data(
    login_session: LoginSessionModel,
    user: UserModel,
) -> LoginSessionData:
    return LoginSessionData(
        session_row_id=login_session.id,
        token_hash=login_session.token_hash,
        user_id=user.id,
        user_name=user.user_name,
        user_state=user.user_state,
        expires_at=login_session.expires_at,
    )

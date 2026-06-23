from __future__ import annotations

from datetime import datetime
from typing import Protocol


class AccountUserLike(Protocol):
    """ユースケースが参照するアカウント情報。"""

    @property
    def user_id(self) -> str: ...

    @property
    def user_name(self) -> str: ...

    @property
    def password_hash(self) -> str: ...

    @property
    def user_state(self) -> str: ...


class LoginSessionLike(Protocol):
    """ユースケースが参照するログインセッション情報。"""

    @property
    def session_row_id(self) -> int: ...

    @property
    def token_hash(self) -> str: ...

    @property
    def user_id(self) -> str: ...

    @property
    def user_name(self) -> str: ...

    @property
    def user_state(self) -> str: ...

    @property
    def expires_at(self) -> datetime: ...


class AccountRepositoryLike(Protocol):
    """F002ユースケースが必要とするRepository境界。"""

    def create_user(
        self,
        user_id: str,
        user_name: str,
        password_hash: str,
        created_at: datetime,
    ) -> AccountUserLike: ...

    def get_user_for_login(self, user_id: str) -> AccountUserLike | None: ...

    def update_user_name(
        self,
        user_id: str,
        user_name: str,
        updated_at: datetime,
    ) -> AccountUserLike | None: ...

    def update_password_hash(
        self,
        user_id: str,
        password_hash: str,
        updated_at: datetime,
    ) -> None: ...

    def create_login_session(
        self,
        token_hash: str,
        user_id: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> LoginSessionLike: ...

    def find_session_by_token_hash(
        self,
        token_hash: str,
    ) -> LoginSessionLike | None: ...

    def delete_session_by_token_hash(self, token_hash: str) -> int: ...

    def delete_sessions_by_user_id(self, user_id: str) -> int: ...

    def mark_user_deleting(
        self,
        user_id: str,
        updated_at: datetime,
    ) -> str | None: ...

    def mark_user_chats_deleting(self, user_id: str, updated_at: datetime) -> int: ...

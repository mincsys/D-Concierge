from __future__ import annotations

from typing import Protocol


class PasswordHasherPort(Protocol):
    """パスワードハッシュ化境界。"""

    def hash_password(self, raw_password: str) -> str: ...

    def verify_password(self, raw_password: str, password_hash: str) -> bool: ...


class SessionTokenProviderPort(Protocol):
    """ログインセッショントークン発行境界。"""

    def issue_token(self) -> str: ...

    def hash_token(self, raw_token: str) -> str: ...

from __future__ import annotations

from passlib.context import CryptContext

_PASSWORD_CONTEXT = CryptContext(schemes=("bcrypt",), deprecated="auto")


class PasslibPasswordHasher:
    """passlib bcryptによるパスワードハッシュ実装。"""

    def hash_password(self, raw_password: str) -> str:
        return str(_PASSWORD_CONTEXT.hash(raw_password))

    def verify_password(self, raw_password: str, password_hash: str) -> bool:
        return bool(_PASSWORD_CONTEXT.verify(raw_password, password_hash))

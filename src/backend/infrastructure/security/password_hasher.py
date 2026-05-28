from passlib.context import CryptContext


class PasslibPasswordHasher:
    """passlibとbcryptでパスワードをハッシュ化する。"""

    def __init__(self) -> None:
        self._context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, password: str) -> str:
        """パスワード生値から保存用ハッシュを生成する。"""
        return self._context.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """パスワード生値と保存済みハッシュの一致を返す。"""
        return self._context.verify(password, password_hash)

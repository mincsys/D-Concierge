from typing import Protocol


class PasswordHasherPort(Protocol):
    """パスワードハッシュ生成・検証境界。"""

    def hash_password(self, password: str) -> str:
        """パスワード生値から保存用ハッシュを生成する。"""

    def verify_password(self, password: str, password_hash: str) -> bool:
        """パスワード生値と保存済みハッシュの一致を返す。"""


class SessionTokenProviderPort(Protocol):
    """ログインセッショントークン境界。"""

    def issue_token(self) -> str:
        """Cookieへ設定する推測困難なトークン生値を発行する。"""

    def hash_token(self, token: str) -> str:
        """トークン生値からDB照合用ハッシュを生成する。"""

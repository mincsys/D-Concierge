import hashlib
import secrets


class SecretsSessionTokenProvider:
    """secretsでCookie用トークンを発行する。"""

    def issue_token(self) -> str:
        """推測困難なトークン生値を発行する。"""
        return secrets.token_urlsafe(48)

    def hash_token(self, token: str) -> str:
        """トークン生値からDB照合用ハッシュを生成する。"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

from __future__ import annotations

from hashlib import sha256
from secrets import token_urlsafe


class SecretsSessionTokenProvider:
    """Cookie用生トークンとDB照合用ハッシュを扱う実装。"""

    def issue_token(self) -> str:
        return token_urlsafe(48)

    def hash_token(self, raw_token: str) -> str:
        digest = sha256(raw_token.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

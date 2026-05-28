from backend.infrastructure.security.password_hasher import PasslibPasswordHasher
from backend.infrastructure.security.session_token_provider import (
    SecretsSessionTokenProvider,
)


def test_session_token_provider_issues_raw_token_and_hashes_deterministically() -> None:
    """観点：U-ACC-004。確認：Cookie用生値とDB照合用ハッシュを分離する。"""
    provider = SecretsSessionTokenProvider()

    token = provider.issue_token()

    assert token
    assert provider.hash_token(token) == provider.hash_token(token)
    assert provider.hash_token(token) != token


def test_password_hasher_hashes_and_verifies_without_plaintext_storage() -> None:
    """観点：U-ACC-005。確認：パスワード生値を保存用ハッシュへ変換し検証できる。"""
    hasher = PasslibPasswordHasher()

    password_hash = hasher.hash_password("abc12")

    assert password_hash != "abc12"
    assert hasher.verify_password("abc12", password_hash)
    assert not hasher.verify_password("wrong1", password_hash)

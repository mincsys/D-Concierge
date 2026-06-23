from __future__ import annotations


def test_passlib_password_hasher_hashes_and_verifies_without_plaintext() -> None:
    """
    観点：PasswordHasher IFの具象実装がパスワード生値を保存値にしないこと
    確認：hash_passwordは生パスワードとは異なるハッシュを返し、
    verify_passwordは一致と不一致を真偽値だけで返すこと
    """
    from backend.infrastructure.security.password_hasher import PasslibPasswordHasher

    hasher = PasslibPasswordHasher()
    password_hash = hasher.hash_password("raw-password")

    assert password_hash != "raw-password"
    assert "raw-password" not in password_hash
    assert hasher.verify_password("raw-password", password_hash)
    assert not hasher.verify_password("wrong-password", password_hash)


def test_secrets_session_token_provider_issues_raw_token_and_hashes_for_db() -> None:
    """
    観点：SessionTokenProvider IFの具象実装がCookie用生トークンと
    DB照合用ハッシュを分離すること
    確認：issue_tokenは推測困難な別値を発行し、hash_tokenは同一生トークンに決定的で、
    生トークンそのものを返さないこと
    """
    from backend.infrastructure.security.session_token import (
        SecretsSessionTokenProvider,
    )

    provider = SecretsSessionTokenProvider()

    first_token = provider.issue_token()
    second_token = provider.issue_token()
    first_hash = provider.hash_token(first_token)

    assert first_token != second_token
    assert len(first_token) >= 32
    assert first_hash == provider.hash_token(first_token)
    assert first_hash != first_token
    assert first_token not in first_hash

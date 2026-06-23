from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.shared.tracing.trace_id import TraceId
from backend.tests.support.account import (
    FIXED_NOW,
    TRACE_ID_VALUE,
    AccountUserRecord,
    FakeAccountRepository,
    FakeSessionTokenProvider,
    FakeTransactionManager,
    FixedClock,
    LoginSessionRecord,
)


def test_authenticate_session_returns_user_for_valid_active_session() -> None:
    """
    観点：認証状態確認ユースケースがCookieトークンを照合用ハッシュで検証すること
    確認：有効期限内かつactiveユーザのセッションでは認証済みユーザを返し、
    Cookie生値をRepository検索へ渡さないこと
    """
    from backend.application.account.authenticate_session import (
        AuthenticateSessionCommand,
        AuthenticateSessionUseCase,
    )

    repository = _repository_with_session(
        token_hash="valid-token-hash",
        user_state="active",
        expires_at=FIXED_NOW + timedelta(minutes=1),
    )
    token_provider = FakeSessionTokenProvider(
        token_hashes={"valid-raw-token": "valid-token-hash"},
    )
    use_case = AuthenticateSessionUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        session_token_provider=token_provider,
        clock=FixedClock(FIXED_NOW),
    )

    result = use_case.execute(
        AuthenticateSessionCommand(
            session_token="valid-raw-token",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.user_id == "user-001"
    assert result.user_name == "利用者"
    assert repository.deleted_session_hashes == []
    assert token_provider.hashed_tokens == ["valid-raw-token"]


@pytest.mark.parametrize(
    ("session_token", "token_hash", "expires_at", "user_state"),
    (
        (None, "missing-token-hash", FIXED_NOW + timedelta(minutes=1), "active"),
        (
            "expired-raw-token",
            "expired-token-hash",
            FIXED_NOW - timedelta(seconds=1),
            "active",
        ),
        (
            "deleting-raw-token",
            "deleting-token-hash",
            FIXED_NOW + timedelta(minutes=1),
            "deleting",
        ),
    ),
)
def test_authenticate_session_rejects_missing_expired_or_deleting_session(
    session_token: str | None,
    token_hash: str,
    expires_at: datetime,
    user_state: str,
) -> None:
    """
    観点：未ログイン、期限切れ、削除中ユーザのセッションが保護対象APIへ渡らないこと
    確認：未ログインエラーを返し、期限切れまたは削除中ユーザのセッション行は
    token_hashで削除し、Cookie生値は保存しないこと
    """
    from backend.application.account.authenticate_session import (
        AuthenticateSessionCommand,
        AuthenticateSessionUseCase,
    )
    from backend.application.account.errors import AuthenticationRequiredError

    repository = _repository_with_session(
        token_hash=token_hash,
        user_state=user_state,
        expires_at=expires_at,
    )
    token_provider = FakeSessionTokenProvider(
        token_hashes={
            "expired-raw-token": "expired-token-hash",
            "deleting-raw-token": "deleting-token-hash",
        },
    )
    use_case = AuthenticateSessionUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        session_token_provider=token_provider,
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(AuthenticationRequiredError):
        use_case.execute(
            AuthenticateSessionCommand(
                session_token=session_token,
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    if session_token is None:
        assert repository.deleted_session_hashes == []
    else:
        assert repository.deleted_session_hashes == [token_hash]


def test_authenticate_session_rejects_unknown_cookie_without_delete() -> None:
    """
    観点：認証状態確認ユースケースがCookieありでもDBセッションなしを未ログイン扱いにすること
    確認：未ログインエラーを返し、存在しないtoken_hashの削除依頼やCookie生値保存を行わないこと
    """
    from backend.application.account.authenticate_session import (
        AuthenticateSessionCommand,
        AuthenticateSessionUseCase,
    )
    from backend.application.account.errors import AuthenticationRequiredError

    repository = FakeAccountRepository()
    token_provider = FakeSessionTokenProvider(
        token_hashes={"unknown-raw-token": "unknown-token-hash"},
    )
    use_case = AuthenticateSessionUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        session_token_provider=token_provider,
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(AuthenticationRequiredError):
        use_case.execute(
            AuthenticateSessionCommand(
                session_token="unknown-raw-token",
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert repository.deleted_session_hashes == []
    assert token_provider.hashed_tokens == ["unknown-raw-token"]


def test_logout_deletes_only_current_session_hash_and_accepts_missing_cookie() -> None:
    """
    観点：ログアウトユースケースが現在Cookieに対応するセッションだけを削除すること
    確認：Cookieありではtoken_hash削除を行い、CookieなしではRepositoryを呼ばず正常終了すること
    """
    from backend.application.account.logout import LogoutCommand, LogoutUseCase

    repository = _repository_with_session(
        token_hash="current-token-hash",
        user_state="active",
        expires_at=FIXED_NOW + timedelta(minutes=1),
    )
    token_provider = FakeSessionTokenProvider(
        token_hashes={"current-raw-token": "current-token-hash"},
    )
    use_case = LogoutUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        session_token_provider=token_provider,
    )

    use_case.execute(
        LogoutCommand(
            session_token="current-raw-token",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )
    use_case.execute(
        LogoutCommand(
            session_token=None,
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert repository.deleted_session_hashes == ["current-token-hash"]
    assert token_provider.hashed_tokens == ["current-raw-token"]


def _repository_with_session(
    *,
    token_hash: str,
    user_state: str,
    expires_at: datetime,
) -> FakeAccountRepository:
    repository = FakeAccountRepository(
        users={
            "user-001": AccountUserRecord(
                user_id="user-001",
                user_name="利用者",
                password_hash="stored-password-hash",
                user_state=user_state,
            ),
        },
    )
    repository.sessions[token_hash] = LoginSessionRecord(
        session_row_id=1,
        token_hash=token_hash,
        user_id="user-001",
        user_name="利用者",
        user_state=user_state,
        expires_at=expires_at,
    )
    return repository

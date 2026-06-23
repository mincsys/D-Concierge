from __future__ import annotations

import pytest

from backend.shared.tracing.trace_id import TraceId
from backend.tests.support.account import (
    FIXED_NOW,
    SESSION_EXPIRES_AT,
    TRACE_ID_VALUE,
    AccountUserRecord,
    FakeAccountRepository,
    FakePasswordHasher,
    FakeSessionTokenProvider,
    FakeTransactionManager,
    FixedClock,
)


def test_register_account_creates_user_and_session_with_hashed_values() -> None:
    """
    観点：アカウント登録ユースケースが入力検証、ハッシュ化、セッション発行、永続化を同一責務として調停すること
    確認：usersにはactiveユーザ、login_sessionsには照合用token_hashだけが保存され、
    既存Cookieセッションは削除され、Cookie返却用の生トークンだけが結果へ返ること
    """
    from backend.application.account.register_account import (
        RegisterAccountCommand,
        RegisterAccountUseCase,
    )

    repository = FakeAccountRepository()
    token_provider = FakeSessionTokenProvider(
        issued_token="new-raw-token",
        token_hashes={
            "new-raw-token": "new-token-hash",
            "old-raw-token": "old-token-hash",
        },
    )
    use_case = RegisterAccountUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=FakePasswordHasher(),
        session_token_provider=token_provider,
        clock=FixedClock(FIXED_NOW),
    )

    result = use_case.execute(
        RegisterAccountCommand(
            user_id="user-001",
            user_name="利用者",
            password="raw-password",
            password_confirmation="raw-password",
            existing_session_token="old-raw-token",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.user.user_id == "user-001"
    assert result.user.user_name == "利用者"
    assert result.session_token == "new-raw-token"
    assert result.expires_at == SESSION_EXPIRES_AT
    assert repository.created_users == [
        AccountUserRecord(
            user_id="user-001",
            user_name="利用者",
            password_hash="hashed-password-1",
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
    ]
    assert repository.created_sessions[0].token_hash == "new-token-hash"
    assert repository.created_sessions[0].user_id == "user-001"
    assert repository.deleted_session_hashes == ["old-token-hash"]
    assert "raw-password" not in _repository_saved_secret_values(repository)
    assert "new-raw-token" not in _repository_saved_secret_values(repository)


def test_register_account_rejects_duplicate_user_id_without_side_effects() -> None:
    """
    観点：アカウント登録の重複ユーザIDが項目別入力エラーとして扱われること
    確認：既存ユーザIDの場合はuser_idのfield_errorsを返し、パスワードハッシュ化、
    セッション発行、ユーザ作成、既存セッション削除を行わないこと
    """
    from backend.application.account.errors import FieldValidationError
    from backend.application.account.register_account import (
        RegisterAccountCommand,
        RegisterAccountUseCase,
    )

    repository = FakeAccountRepository(
        users={
            "user-001": AccountUserRecord(
                user_id="user-001",
                user_name="既存利用者",
                password_hash="stored-hash",
            ),
        },
    )
    password_hasher = FakePasswordHasher()
    token_provider = FakeSessionTokenProvider()
    use_case = RegisterAccountUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=password_hasher,
        session_token_provider=token_provider,
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            RegisterAccountCommand(
                user_id="user-001",
                user_name="利用者",
                password="raw-password",
                password_confirmation="raw-password",
                existing_session_token=None,
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert "user_id" in raised.value.field_errors
    assert password_hasher.hashed_passwords == []
    assert token_provider.issued_count == 0
    assert repository.created_users == []
    assert repository.created_sessions == []
    assert repository.deleted_session_hashes == []


@pytest.mark.parametrize(
    ("user_id", "user_name", "password", "password_confirmation", "expected_field"),
    (
        ("-invalid", "利用者", "raw-password", "raw-password", "user_id"),
        ("user-001", "", "raw-password", "raw-password", "user_name"),
        ("user-001", "利用者", "1234", "1234", "password"),
        ("user-001", "利用者", "passwordあ", "passwordあ", "password"),
        (
            "user-001",
            "利用者",
            "raw-password",
            "mismatch-password",
            "password_confirmation",
        ),
    ),
)
def test_register_account_rejects_invalid_input_without_side_effects(
    user_id: str,
    user_name: str,
    password: str,
    password_confirmation: str,
    expected_field: str,
) -> None:
    """
    観点：アカウント登録の入力規則がRepository更新前に検証されること
    確認：ユーザID、ユーザ名、パスワード、確認値の不正は該当field_errorsを返し、
    パスワードハッシュ化、セッション発行、ユーザ作成を行わないこと
    """
    from backend.application.account.errors import FieldValidationError
    from backend.application.account.register_account import (
        RegisterAccountCommand,
        RegisterAccountUseCase,
    )

    repository = FakeAccountRepository()
    password_hasher = FakePasswordHasher()
    token_provider = FakeSessionTokenProvider()
    use_case = RegisterAccountUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=password_hasher,
        session_token_provider=token_provider,
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            RegisterAccountCommand(
                user_id=user_id,
                user_name=user_name,
                password=password,
                password_confirmation=password_confirmation,
                existing_session_token=None,
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert expected_field in raised.value.field_errors
    assert password_hasher.hashed_passwords == []
    assert token_provider.issued_count == 0
    assert repository.created_users == []
    assert repository.created_sessions == []


def test_login_replaces_existing_session_and_returns_authenticated_user() -> None:
    """
    観点：ログインユースケースが認証成功時にブラウザ単位のセッションを置き換えること
    確認：保存済みパスワードを検証し、既存Cookieのセッションを削除してから
    新規token_hashを保存し、応答用には生トークンとユーザ情報だけを返すこと
    """
    from backend.application.account.login import LoginCommand, LoginUseCase

    repository = FakeAccountRepository(
        users={
            "user-001": AccountUserRecord(
                user_id="user-001",
                user_name="利用者",
                password_hash="stored-password-hash",
            ),
        },
    )
    token_provider = FakeSessionTokenProvider(
        issued_token="new-login-token",
        token_hashes={
            "new-login-token": "new-login-token-hash",
            "old-login-token": "old-login-token-hash",
        },
    )
    use_case = LoginUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=FakePasswordHasher(
            verify_results={
                ("raw-password", "stored-password-hash"): True,
            },
        ),
        session_token_provider=token_provider,
        clock=FixedClock(FIXED_NOW),
    )

    result = use_case.execute(
        LoginCommand(
            user_id="user-001",
            password="raw-password",
            existing_session_token="old-login-token",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.user.user_id == "user-001"
    assert result.user.user_name == "利用者"
    assert result.session_token == "new-login-token"
    assert result.expires_at == SESSION_EXPIRES_AT
    assert repository.deleted_session_hashes == ["old-login-token-hash"]
    assert repository.created_sessions[0].token_hash == "new-login-token-hash"
    assert "raw-password" not in _repository_saved_secret_values(repository)
    assert "new-login-token" not in _repository_saved_secret_values(repository)


@pytest.mark.parametrize(
    ("stored_user", "verify_result", "expected_field"),
    (
        (None, False, "user_id"),
        (
            AccountUserRecord(
                user_id="user-001",
                user_name="削除中利用者",
                password_hash="stored-password-hash",
                user_state="deleting",
            ),
            True,
            "user_id",
        ),
        (
            AccountUserRecord(
                user_id="user-001",
                user_name="利用者",
                password_hash="stored-password-hash",
            ),
            False,
            "password",
        ),
    ),
)
def test_login_rejects_invalid_credentials_without_session_creation(
    stored_user: AccountUserRecord | None,
    verify_result: bool,
    expected_field: str,
) -> None:
    """
    観点：ログイン失敗時にユーザID不存在、削除中ユーザ、パスワード不一致を項目別エラーへ分離すること
    確認：失敗時は該当field_errorsを返し、新規セッション作成と既存セッション削除を行わないこと
    """
    from backend.application.account.errors import FieldValidationError
    from backend.application.account.login import LoginCommand, LoginUseCase

    users: dict[str, AccountUserRecord] = {}
    if stored_user is not None:
        users[stored_user.user_id] = stored_user
    repository = FakeAccountRepository(users=users)
    use_case = LoginUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=FakePasswordHasher(
            verify_results={
                ("raw-password", "stored-password-hash"): verify_result,
            },
        ),
        session_token_provider=FakeSessionTokenProvider(),
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            LoginCommand(
                user_id="user-001",
                password="raw-password",
                existing_session_token="old-login-token",
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert expected_field in raised.value.field_errors
    assert repository.created_sessions == []
    assert repository.deleted_session_hashes == []


def _repository_saved_secret_values(
    repository: FakeAccountRepository,
) -> tuple[str, ...]:
    user_password_hashes = tuple(
        user.password_hash for user in repository.users.values()
    )
    session_token_hashes = tuple(
        session.token_hash for session in repository.sessions.values()
    )
    return user_password_hashes + session_token_hashes

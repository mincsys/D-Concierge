from __future__ import annotations

from datetime import timedelta

import pytest

from backend.shared.tracing.trace_id import TraceId
from backend.tests.support.account import (
    FIXED_NOW,
    TRACE_ID_VALUE,
    AccountUserRecord,
    DispatchResultRecord,
    FakeAccountDeletionDispatcher,
    FakeAccountRepository,
    FakePasswordHasher,
    FakeTraceLogger,
    FakeTransactionManager,
    FixedClock,
    LoginSessionRecord,
)


def test_change_user_name_updates_only_active_user_name() -> None:
    """
    観点：ユーザ名変更ユースケースが認証済みactiveユーザの表示名だけを更新すること
    確認：戻り値は更新後のユーザ情報となり、パスワードハッシュとログインセッションは変更しないこと
    """
    from backend.application.account.change_user_name import (
        ChangeUserNameCommand,
        ChangeUserNameUseCase,
    )

    repository = _repository_with_active_user()
    repository.sessions["session-token-hash"] = LoginSessionRecord(
        session_row_id=1,
        token_hash="session-token-hash",
        user_id="user-001",
        user_name="利用者",
        user_state="active",
        expires_at=FIXED_NOW + timedelta(minutes=1),
    )
    use_case = ChangeUserNameUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        clock=FixedClock(FIXED_NOW),
    )

    result = use_case.execute(
        ChangeUserNameCommand(
            authenticated_user_id="user-001",
            user_name="変更後利用者",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.user_id == "user-001"
    assert result.user_name == "変更後利用者"
    assert repository.users["user-001"].password_hash == "stored-password-hash"
    assert tuple(repository.sessions) == ("session-token-hash",)


@pytest.mark.parametrize("invalid_user_name", ("", "x" * 31))
def test_change_user_name_rejects_invalid_user_name_without_update(
    invalid_user_name: str,
) -> None:
    """
    観点：ユーザ名変更ユースケースがユーザ名入力規則違反を項目別エラーにすること
    確認：user_nameのfield_errorsを返し、users.user_name、password_hash、
    login_sessionsを変更しないこと
    """
    from backend.application.account.change_user_name import (
        ChangeUserNameCommand,
        ChangeUserNameUseCase,
    )
    from backend.application.account.errors import FieldValidationError

    repository = _repository_with_active_user()
    repository.sessions["session-token-hash"] = LoginSessionRecord(
        session_row_id=1,
        token_hash="session-token-hash",
        user_id="user-001",
        user_name="利用者",
        user_state="active",
        expires_at=FIXED_NOW + timedelta(minutes=1),
    )
    original_user = repository.users["user-001"]
    use_case = ChangeUserNameUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            ChangeUserNameCommand(
                authenticated_user_id="user-001",
                user_name=invalid_user_name,
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert "user_name" in raised.value.field_errors
    assert repository.users["user-001"] == original_user
    assert tuple(repository.sessions) == ("session-token-hash",)


def test_change_user_name_rejects_deleted_authenticated_user_without_update() -> None:
    """
    観点：ユーザ名変更ユースケースが認証後に通常操作不可となったユーザを更新しないこと
    確認：Repositoryが更新対象なしを返した場合はuser_nameのfield_errorsを返し、
    usersとlogin_sessionsを変更しないこと
    """
    from backend.application.account.change_user_name import (
        ChangeUserNameCommand,
        ChangeUserNameUseCase,
    )
    from backend.application.account.errors import FieldValidationError

    repository = FakeAccountRepository(
        users={
            "user-001": AccountUserRecord(
                user_id="user-001",
                user_name="削除中利用者",
                password_hash="stored-password-hash",
                user_state="deleting",
            ),
        },
    )
    original_user = repository.users["user-001"]
    use_case = ChangeUserNameUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            ChangeUserNameCommand(
                authenticated_user_id="user-001",
                user_name="変更後利用者",
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert "user_name" in raised.value.field_errors
    assert repository.users["user-001"] == original_user
    assert repository.sessions == {}


def test_change_password_verifies_current_password_and_keeps_sessions() -> None:
    """
    観点：パスワード変更ユースケースが現在パスワード一致時だけ新ハッシュを保存すること
    確認：current_passwordを保存済みハッシュで検証し、新パスワードハッシュだけを更新し、
    現在および他のログインセッションを削除しないこと
    """
    from backend.application.account.change_password import (
        ChangePasswordCommand,
        ChangePasswordUseCase,
    )

    repository = _repository_with_active_user()
    repository.sessions["current-token-hash"] = LoginSessionRecord(
        session_row_id=1,
        token_hash="current-token-hash",
        user_id="user-001",
        user_name="利用者",
        user_state="active",
        expires_at=FIXED_NOW + timedelta(minutes=1),
    )
    hasher = FakePasswordHasher(
        verify_results={
            ("current-password", "stored-password-hash"): True,
        },
    )
    use_case = ChangePasswordUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=hasher,
        clock=FixedClock(FIXED_NOW),
    )

    use_case.execute(
        ChangePasswordCommand(
            authenticated_user_id="user-001",
            current_password="current-password",
            new_password="new-password",
            new_password_confirmation="new-password",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert hasher.verified_passwords == [
        ("current-password", "stored-password-hash"),
    ]
    assert repository.password_updates == [("user-001", "hashed-password-1")]
    assert tuple(repository.sessions) == ("current-token-hash",)
    assert repository.deleted_session_hashes == []
    assert repository.deleted_session_user_ids == []


def test_change_password_rejects_current_password_mismatch_without_update() -> None:
    """
    観点：現在パスワード不一致が項目別入力エラーとして扱われること
    確認：current_passwordのfield_errorsを返し、新パスワードハッシュ生成とDB更新を行わないこと
    """
    from backend.application.account.change_password import (
        ChangePasswordCommand,
        ChangePasswordUseCase,
    )
    from backend.application.account.errors import FieldValidationError

    repository = _repository_with_active_user()
    hasher = FakePasswordHasher(
        verify_results={
            ("wrong-password", "stored-password-hash"): False,
        },
    )
    use_case = ChangePasswordUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=hasher,
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            ChangePasswordCommand(
                authenticated_user_id="user-001",
                current_password="wrong-password",
                new_password="new-password",
                new_password_confirmation="new-password",
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert "current_password" in raised.value.field_errors
    assert repository.password_updates == []
    assert hasher.hashed_passwords == []


def test_change_password_rejects_deleted_authenticated_user_without_hashing() -> None:
    """
    観点：パスワード変更ユースケースが認証後に通常操作不可となったユーザを更新しないこと
    確認：deletingユーザではcurrent_passwordのfield_errorsを返し、
    現在パスワード検証、新ハッシュ生成、password_hash更新を行わないこと
    """
    from backend.application.account.change_password import (
        ChangePasswordCommand,
        ChangePasswordUseCase,
    )
    from backend.application.account.errors import FieldValidationError

    repository = FakeAccountRepository(
        users={
            "user-001": AccountUserRecord(
                user_id="user-001",
                user_name="削除中利用者",
                password_hash="stored-password-hash",
                user_state="deleting",
            ),
        },
    )
    hasher = FakePasswordHasher()
    use_case = ChangePasswordUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=hasher,
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            ChangePasswordCommand(
                authenticated_user_id="user-001",
                current_password="current-password",
                new_password="new-password",
                new_password_confirmation="new-password",
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert "current_password" in raised.value.field_errors
    assert hasher.verified_passwords == []
    assert hasher.hashed_passwords == []
    assert repository.password_updates == []


@pytest.mark.parametrize(
    ("new_password", "new_password_confirmation", "expected_field"),
    (
        ("1234", "1234", "new_password"),
        ("passwordあ", "passwordあ", "new_password"),
        ("new-password", "mismatch-password", "new_password_confirmation"),
    ),
)
def test_change_password_rejects_new_password_validation_without_update(
    new_password: str,
    new_password_confirmation: str,
    expected_field: str,
) -> None:
    """
    観点：パスワード変更ユースケースが新パスワード制約と確認不一致を分離すること
    確認：new_passwordまたはnew_password_confirmationのfield_errorsを返し、
    password_hashを更新せず、新パスワードハッシュ生成も行わないこと
    """
    from backend.application.account.change_password import (
        ChangePasswordCommand,
        ChangePasswordUseCase,
    )
    from backend.application.account.errors import FieldValidationError

    repository = _repository_with_active_user()
    hasher = FakePasswordHasher(
        verify_results={
            ("current-password", "stored-password-hash"): True,
        },
    )
    use_case = ChangePasswordUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        password_hasher=hasher,
        clock=FixedClock(FIXED_NOW),
    )

    with pytest.raises(FieldValidationError) as raised:
        use_case.execute(
            ChangePasswordCommand(
                authenticated_user_id="user-001",
                current_password="current-password",
                new_password=new_password,
                new_password_confirmation=new_password_confirmation,
                trace_id=TraceId(TRACE_ID_VALUE),
            ),
        )

    assert expected_field in raised.value.field_errors
    assert repository.password_updates == []
    assert hasher.hashed_passwords == []
    assert repository.users["user-001"].password_hash == "stored-password-hash"


def test_delete_account_marks_user_and_chats_deleting_then_dispatches_job() -> None:
    """
    観点：アカウント削除受付ユースケースが論理削除と物理削除登録を分離すること
    確認：ユーザと全チャットをdeletingへ更新し、全ログインセッションを削除した後、
    物理削除ジョブをtrace_id付きで登録してaccount_state=deletingを返すこと
    """
    from backend.application.account.delete_account import (
        DeleteAccountCommand,
        DeleteAccountUseCase,
    )

    repository = _repository_with_active_user()
    repository.sessions["first-token-hash"] = LoginSessionRecord(
        session_row_id=1,
        token_hash="first-token-hash",
        user_id="user-001",
        user_name="利用者",
        user_state="active",
        expires_at=FIXED_NOW + timedelta(minutes=1),
    )
    dispatcher = FakeAccountDeletionDispatcher()
    use_case = DeleteAccountUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=dispatcher,
        trace_logger=FakeTraceLogger(),
        clock=FixedClock(FIXED_NOW),
    )

    result = use_case.execute(
        DeleteAccountCommand(
            authenticated_user_id="user-001",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.account_state == "deleting"
    assert repository.users["user-001"].user_state == "deleting"
    assert repository.chat_deleting_user_ids == ["user-001"]
    assert repository.deleted_session_user_ids == ["user-001"]
    assert repository.sessions == {}
    assert dispatcher.dispatched == [("user-001", TRACE_ID_VALUE)]


def test_delete_account_keeps_deleting_state_when_dispatcher_fails() -> None:
    """
    観点：物理削除ジョブ登録失敗時も削除受付済み状態を巻き戻さないこと
    確認：Dispatcherがfailedを返してもaccount_state=deletingを返し、
    対象ユーザをdeletingのまま維持して診断情報をトレースログへ渡すこと
    """
    from backend.application.account.delete_account import (
        DeleteAccountCommand,
        DeleteAccountUseCase,
    )

    repository = _repository_with_active_user()
    trace_logger = FakeTraceLogger()
    use_case = DeleteAccountUseCase(
        repository=repository,
        transaction_manager=FakeTransactionManager(),
        dispatcher=FakeAccountDeletionDispatcher(
            next_result=DispatchResultRecord(
                status="failed",
                diagnostic_message="background submit failed",
            ),
        ),
        trace_logger=trace_logger,
        clock=FixedClock(FIXED_NOW),
    )

    result = use_case.execute(
        DeleteAccountCommand(
            authenticated_user_id="user-001",
            trace_id=TraceId(TRACE_ID_VALUE),
        ),
    )

    assert result.account_state == "deleting"
    assert repository.users["user-001"].user_state == "deleting"
    assert trace_logger.events[0].user_id == "user-001"
    assert trace_logger.events[0].trace_id == TRACE_ID_VALUE
    assert "background submit failed" in trace_logger.events[0].diagnostic_message


def _repository_with_active_user() -> FakeAccountRepository:
    return FakeAccountRepository(
        users={
            "user-001": AccountUserRecord(
                user_id="user-001",
                user_name="利用者",
                password_hash="stored-password-hash",
                user_state="active",
            ),
        },
    )

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from backend.application.account.authenticate_session import AuthenticateSessionUseCase
from backend.application.account.change_password import ChangePasswordUseCase
from backend.application.account.change_user_name import ChangeUserNameUseCase
from backend.application.account.delete_account import DeleteAccountUseCase
from backend.application.account.login import LoginUseCase
from backend.application.account.logout import LogoutUseCase
from backend.application.account.register_account import RegisterAccountUseCase
from backend.application.ports.database.dto import (
    AccountDeletionTarget,
    AccountUserData,
    AuthenticatedUser,
    LoginSessionData,
)
from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.dto import DispatchResult
from backend.domain.account.user_state import UserState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError, FieldValidationError
from backend.shared.user_messages import PASSWORD_FORMAT_MESSAGE

_NOW = datetime(2026, 5, 27, 0, 0, tzinfo=UTC)


def test_authenticate_session_returns_user_for_valid_session() -> None:
    """観点：U-ACC-006。確認：有効な通常ユーザのセッションを認証済みにする。"""
    repository = RecordingAccountRepository()
    token_provider = FixedTokenProvider()
    session = LoginSessionData(
        session_id=1,
        token_hash="hash-token",
        user_id="demo-user",
        user_name="デモユーザ",
        user_state=UserState.ACTIVE,
        expires_at=_NOW + timedelta(days=1),
    )
    repository.sessions_by_hash["hash-token"] = session
    usecase = AuthenticateSessionUseCase(
        repository=repository,
        token_provider=token_provider,
        clock=FixedClock(_NOW),
    )

    authenticated = usecase.execute("token", trace_id="trace-auth")

    assert authenticated == AuthenticatedUser(
        user_id="demo-user",
        user_name="デモユーザ",
    )
    assert repository.deleted_session_hashes == []


@pytest.mark.parametrize(
    "session",
    [
        None,
        LoginSessionData(
            session_id=1,
            token_hash="hash-token",
            user_id="demo-user",
            user_name="デモユーザ",
            user_state=UserState.ACTIVE,
            expires_at=_NOW - timedelta(seconds=1),
        ),
        LoginSessionData(
            session_id=1,
            token_hash="hash-token",
            user_id="demo-user",
            user_name="デモユーザ",
            user_state=UserState.DELETING,
            expires_at=_NOW + timedelta(days=1),
        ),
    ],
)
def test_authenticate_session_rejects_missing_expired_and_deleting_user(
    session: LoginSessionData | None,
) -> None:
    """観点：U-ACC-007。確認：無効なセッションを未ログイン扱いにする。"""
    repository = RecordingAccountRepository()
    if session is not None:
        repository.sessions_by_hash["hash-token"] = session
    usecase = AuthenticateSessionUseCase(
        repository=repository,
        token_provider=FixedTokenProvider(),
        clock=FixedClock(_NOW),
    )

    with pytest.raises(AppError) as error_info:
        usecase.execute("token", trace_id="trace-auth")

    assert error_info.value.error_type is ErrorType.UNAUTHORIZED
    if session is None:
        assert repository.deleted_session_hashes == []
    else:
        assert repository.deleted_session_hashes == ["hash-token"]


def test_register_account_validates_fields_and_duplicate_without_persistence() -> None:
    """観点：U-ACC-008。確認：登録入力不正と重複を項目別エラーにする。"""
    repository = RecordingAccountRepository()
    repository.users["demo-user"] = AccountUserData(
        user_id="demo-user",
        user_name="既存",
        password_hash="hash",
        user_state=UserState.ACTIVE,
    )
    usecase = RegisterAccountUseCase(
        repository=repository,
        password_hasher=FixedPasswordHasher(),
        token_provider=FixedTokenProvider(),
        clock=FixedClock(_NOW),
    )

    with pytest.raises(FieldValidationError) as error_info:
        usecase.execute(
            user_id="demo-user",
            user_name="",
            password="abc12",
            password_confirmation="zzzzz",
            existing_session_token=None,
            trace_id="trace-register",
        )

    assert error_info.value.field_errors == {
        "user_id": "このユーザIDは既に使用されています。",
        "user_name": "ユーザ名を入力してください。",
        "password_confirmation": "同じパスワードを入力してください。",
    }
    assert repository.created_users == []


def test_register_account_creates_user_and_session_transactionally() -> None:
    """観点：U-ACC-009。確認：登録成功時にユーザとセッションを作成する。"""
    repository = RecordingAccountRepository()
    transaction_manager = RecordingTransactionManager()
    usecase = RegisterAccountUseCase(
        repository=repository,
        password_hasher=FixedPasswordHasher(),
        token_provider=FixedTokenProvider(),
        clock=FixedClock(_NOW),
        transaction_manager=transaction_manager,
    )

    result = usecase.execute(
        user_id="demo-user",
        user_name="デモユーザ",
        password="abc12",
        password_confirmation="abc12",
        existing_session_token="old-token",
        trace_id="trace-register",
    )

    assert result.user == AuthenticatedUser("demo-user", "デモユーザ")
    assert result.session_token == "token"
    assert repository.created_users == [("demo-user", "デモユーザ", "hashed:abc12")]
    assert repository.deleted_session_hashes == ["hash-old-token"]
    assert repository.created_sessions == [
        ("hash-token", "demo-user", _NOW + timedelta(days=400))
    ]
    assert transaction_manager.completed_transactions == [("enter", 1), ("exit", 1)]


def test_login_rejects_missing_user_deleting_user_and_password_mismatch() -> None:
    """観点：U-ACC-010。確認：ログイン失敗時にセッションを作成しない。"""
    repository = RecordingAccountRepository()
    repository.users["deleting"] = AccountUserData(
        user_id="deleting",
        user_name="削除中",
        password_hash="hashed:abc12",
        user_state=UserState.DELETING,
    )
    repository.users["demo-user"] = AccountUserData(
        user_id="demo-user",
        user_name="デモユーザ",
        password_hash="hashed:abc12",
        user_state=UserState.ACTIVE,
    )
    usecase = LoginUseCase(
        repository=repository,
        password_hasher=FixedPasswordHasher(),
        token_provider=FixedTokenProvider(),
        clock=FixedClock(_NOW),
    )

    with pytest.raises(FieldValidationError) as missing:
        usecase.execute("missing", "abc12", None, "trace-login")
    with pytest.raises(FieldValidationError) as deleting:
        usecase.execute("deleting", "abc12", None, "trace-login")
    with pytest.raises(FieldValidationError) as mismatch:
        usecase.execute("demo-user", "wrong1", None, "trace-login")

    assert missing.value.field_errors == {
        "user_id": "入力されたユーザIDは登録されていません。"
    }
    assert deleting.value.field_errors == {
        "user_id": "このアカウントは利用できません。"
    }
    assert mismatch.value.field_errors == {"password": "パスワードが正しくありません。"}
    assert repository.created_sessions == []


def test_login_creates_new_session_and_deletes_existing_browser_session() -> None:
    """観点：U-ACC-011。確認：ログイン成功時にブラウザ単位でセッションを置き換える。"""
    repository = RecordingAccountRepository()
    repository.users["demo-user"] = AccountUserData(
        user_id="demo-user",
        user_name="デモユーザ",
        password_hash="hashed:abc12",
        user_state=UserState.ACTIVE,
    )
    usecase = LoginUseCase(
        repository=repository,
        password_hasher=FixedPasswordHasher(),
        token_provider=FixedTokenProvider(),
        clock=FixedClock(_NOW),
    )

    result = usecase.execute("demo-user", "abc12", "old-token", "trace-login")

    assert result.user == AuthenticatedUser("demo-user", "デモユーザ")
    assert result.session_token == "token"
    assert repository.deleted_session_hashes == ["hash-old-token"]
    assert repository.created_sessions == [
        ("hash-token", "demo-user", _NOW + timedelta(days=400))
    ]


def test_logout_deletes_only_current_session_and_allows_missing_token() -> None:
    """観点：U-ACC-012。確認：現在セッションだけを削除し、Cookieなしは正常終了する。"""
    repository = RecordingAccountRepository()
    usecase = LogoutUseCase(repository=repository, token_provider=FixedTokenProvider())

    usecase.execute(None, trace_id="trace-logout")
    usecase.execute("token", trace_id="trace-logout")

    assert repository.deleted_session_hashes == ["hash-token"]


def test_change_user_name_validates_and_updates_only_name() -> None:
    """観点：U-ACC-013。確認：ユーザ名入力を検証し、成功時はユーザ名だけを更新する。"""
    repository = RecordingAccountRepository()
    usecase = ChangeUserNameUseCase(repository=repository)

    with pytest.raises(FieldValidationError) as error_info:
        usecase.execute("demo-user", "", trace_id="trace-name")
    result = usecase.execute("demo-user", "新ユーザ", trace_id="trace-name")

    assert error_info.value.field_errors == {
        "user_name": "ユーザ名を入力してください。"
    }
    assert result == AuthenticatedUser("demo-user", "新ユーザ")
    assert repository.updated_user_names == [("demo-user", "新ユーザ")]


def test_change_password_validates_current_new_and_confirmation() -> None:
    """観点：U-ACC-014。確認：パスワード変更の異常系を項目別エラーにする。"""
    repository = RecordingAccountRepository()
    repository.users["demo-user"] = AccountUserData(
        user_id="demo-user",
        user_name="デモユーザ",
        password_hash="hashed:abc12",
        user_state=UserState.ACTIVE,
    )
    usecase = ChangePasswordUseCase(
        repository=repository,
        password_hasher=FixedPasswordHasher(),
    )

    with pytest.raises(FieldValidationError) as error_info:
        usecase.execute("demo-user", "wrong1", "abcd", "zzzzz", "trace-password")

    assert error_info.value.field_errors == {
        "current_password": "現在のパスワードが正しくありません。",
        "new_password": PASSWORD_FORMAT_MESSAGE,
        "new_password_confirmation": "同じパスワードを入力してください。",
    }
    assert repository.updated_password_hashes == []


def test_change_password_updates_hash_without_deleting_sessions() -> None:
    """観点：U-ACC-015。確認：成功時はパスワードハッシュだけを更新する。"""
    repository = RecordingAccountRepository()
    repository.users["demo-user"] = AccountUserData(
        user_id="demo-user",
        user_name="デモユーザ",
        password_hash="hashed:abc12",
        user_state=UserState.ACTIVE,
    )
    usecase = ChangePasswordUseCase(
        repository=repository,
        password_hasher=FixedPasswordHasher(),
    )

    usecase.execute("demo-user", "abc12", "new12", "new12", "trace-password")

    assert repository.updated_password_hashes == [("demo-user", "hashed:new12")]
    assert repository.deleted_session_hashes == []


def test_delete_account_marks_deleting_and_deletes_all_sessions() -> None:
    """観点：U-ACC-016。確認：削除受付時にユーザ、チャット、全セッションを更新する。"""
    repository = RecordingAccountRepository()
    dispatcher = RecordingAccountDeletionDispatcher()
    transaction_manager = RecordingTransactionManager()
    usecase = DeleteAccountUseCase(
        repository=repository,
        deletion_dispatcher=dispatcher,
        transaction_manager=transaction_manager,
    )

    result = usecase.execute("demo-user", trace_id="trace-delete")

    assert result.account_state is UserState.DELETING
    assert repository.marked_deleting_users == ["demo-user"]
    assert repository.marked_deleting_chat_users == ["demo-user"]
    assert repository.deleted_session_users == ["demo-user"]
    assert dispatcher.registered == [("demo-user", "trace-delete")]
    assert transaction_manager.completed_transactions == [("enter", 1), ("exit", 1)]


@dataclass(frozen=True, slots=True)
class FixedClock:
    now_value: datetime

    def now(self) -> datetime:
        return self.now_value


class FixedTokenProvider:
    def issue_token(self) -> str:
        return "token"

    def hash_token(self, token: str) -> str:
        return f"hash-{token}"


class FixedPasswordHasher:
    def hash_password(self, password: str) -> str:
        return f"hashed:{password}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


@dataclass(slots=True)
class RecordingTransactionManager:
    completed_transactions: list[tuple[str, int]] = field(default_factory=list)
    _next_id: int = 0

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._next_id += 1
        transaction_id = self._next_id
        self.completed_transactions.append(("enter", transaction_id))
        try:
            yield
        finally:
            self.completed_transactions.append(("exit", transaction_id))


@dataclass(slots=True)
class RecordingAccountDeletionDispatcher:
    registered: list[tuple[str, str]] = field(default_factory=list)

    def register(self, user_id: str, trace_id: str = "") -> DispatchResult:
        self.registered.append((user_id, trace_id))
        return DispatchResult(status=DispatchStatus.REGISTERED)


@dataclass(slots=True)
class RecordingAccountRepository:
    users: dict[str, AccountUserData] = field(default_factory=dict)
    sessions_by_hash: dict[str, LoginSessionData] = field(default_factory=dict)
    created_users: list[tuple[str, str, str]] = field(default_factory=list)
    created_sessions: list[tuple[str, str, datetime]] = field(default_factory=list)
    deleted_session_hashes: list[str] = field(default_factory=list)
    deleted_session_users: list[str] = field(default_factory=list)
    updated_user_names: list[tuple[str, str]] = field(default_factory=list)
    updated_password_hashes: list[tuple[str, str]] = field(default_factory=list)
    marked_deleting_users: list[str] = field(default_factory=list)
    marked_deleting_chat_users: list[str] = field(default_factory=list)

    def create_user(
        self, user_id: str, user_name: str, password_hash: str, now: datetime
    ) -> None:
        _ = now
        self.created_users.append((user_id, user_name, password_hash))
        self.users[user_id] = AccountUserData(
            user_id=user_id,
            user_name=user_name,
            password_hash=password_hash,
            user_state=UserState.ACTIVE,
        )

    def get_user_for_login(self, user_id: str) -> AccountUserData | None:
        return self.users.get(user_id)

    def update_user_name(
        self, user_id: str, user_name: str, now: datetime
    ) -> AccountUserData:
        _ = now
        self.updated_user_names.append((user_id, user_name))
        return AccountUserData(
            user_id=user_id,
            user_name=user_name,
            password_hash="hashed:abc12",
            user_state=UserState.ACTIVE,
        )

    def update_password_hash(
        self, user_id: str, password_hash: str, now: datetime
    ) -> None:
        _ = now
        self.updated_password_hashes.append((user_id, password_hash))

    def create_login_session(
        self, token_hash: str, user_id: str, expires_at: datetime, now: datetime
    ) -> LoginSessionData:
        _ = now
        self.created_sessions.append((token_hash, user_id, expires_at))
        return LoginSessionData(
            session_id=len(self.created_sessions),
            token_hash=token_hash,
            user_id=user_id,
            user_name=self.users[user_id].user_name,
            user_state=UserState.ACTIVE,
            expires_at=expires_at,
        )

    def find_session_by_token_hash(self, token_hash: str) -> LoginSessionData | None:
        return self.sessions_by_hash.get(token_hash)

    def delete_session_by_token_hash(self, token_hash: str) -> int:
        self.deleted_session_hashes.append(token_hash)
        self.sessions_by_hash.pop(token_hash, None)
        return 1

    def delete_sessions_by_user_id(self, user_id: str) -> int:
        self.deleted_session_users.append(user_id)
        return 1

    def delete_expired_sessions(self, now: datetime) -> int:
        _ = now
        return 0

    def list_deleting_user_ids(self) -> tuple[str, ...]:
        return ()

    def get_account_deletion_target(self, user_id: str) -> AccountDeletionTarget | None:
        _ = user_id
        return None

    def delete_account_data(self, user_id: str) -> None:
        _ = user_id

    def mark_user_deleting(self, user_id: str, now: datetime) -> None:
        _ = now
        self.marked_deleting_users.append(user_id)

    def mark_user_chats_deleting(self, user_id: str, now: datetime) -> None:
        _ = now
        self.marked_deleting_chat_users.append(user_id)

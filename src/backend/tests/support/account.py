from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType

from backend.application.ports.database.dto import AccountUserData
from backend.application.ports.runtime.interface import AccountDeletionDispatchResult
from backend.application.ports.trace_log.dto import TraceLogRecord

FIXED_NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
SESSION_EXPIRES_AT = FIXED_NOW + timedelta(days=400)
TRACE_ID_VALUE = "018fe2d4-0000-7000-8000-000000000001"


@dataclass(frozen=True, slots=True)
class AccountUserRecord:
    user_id: str
    user_name: str
    password_hash: str
    user_state: str = "active"
    created_at: datetime = FIXED_NOW
    updated_at: datetime = FIXED_NOW


@dataclass(frozen=True, slots=True)
class LoginSessionRecord:
    session_row_id: int
    token_hash: str
    user_id: str
    user_name: str
    user_state: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class DispatchResultRecord:
    status: str
    diagnostic_message: str = ""


@dataclass(frozen=True, slots=True)
class TraceEventRecord:
    event_name: str
    user_id: str
    trace_id: str
    diagnostic_message: str


@dataclass(slots=True)
class FixedClock:
    now: datetime = FIXED_NOW

    def now_utc(self) -> datetime:
        return self.now

    def now_app_timezone(self) -> datetime:
        return self.now


@dataclass(slots=True)
class FakeTransactionManager:
    begin_count: int = 0
    commit_count: int = 0
    rollback_count: int = 0

    def __enter__(self) -> None:
        self.begin_count += 1

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if exc_type is None:
            self.commit_count += 1
        else:
            self.rollback_count += 1
        return None


@dataclass(slots=True)
class FakePasswordHasher:
    verify_results: dict[tuple[str, str], bool] = field(default_factory=dict)
    hashed_passwords: list[str] = field(default_factory=list)
    verified_passwords: list[tuple[str, str]] = field(default_factory=list)

    def hash_password(self, raw_password: str) -> str:
        self.hashed_passwords.append(raw_password)
        return f"hashed-password-{len(self.hashed_passwords)}"

    def verify_password(self, raw_password: str, password_hash: str) -> bool:
        self.verified_passwords.append((raw_password, password_hash))
        configured = self.verify_results.get((raw_password, password_hash))
        if configured is not None:
            return configured
        return password_hash.startswith("hashed-password")


@dataclass(slots=True)
class FakeSessionTokenProvider:
    issued_token: str = "issued-session-token"
    token_hashes: dict[str, str] = field(default_factory=dict)
    issued_count: int = 0
    hashed_tokens: list[str] = field(default_factory=list)

    def issue_token(self) -> str:
        self.issued_count += 1
        return self.issued_token

    def hash_token(self, raw_token: str) -> str:
        self.hashed_tokens.append(raw_token)
        mapped_hash = self.token_hashes.get(raw_token)
        if mapped_hash is not None:
            return mapped_hash
        return f"token-hash-{len(self.hashed_tokens)}"


@dataclass(slots=True)
class FakeAccountRepository:
    users: dict[str, AccountUserRecord] = field(default_factory=dict)
    sessions: dict[str, LoginSessionRecord] = field(default_factory=dict)
    created_users: list[AccountUserRecord] = field(default_factory=list)
    created_sessions: list[LoginSessionRecord] = field(default_factory=list)
    deleted_session_hashes: list[str] = field(default_factory=list)
    deleted_session_user_ids: list[str] = field(default_factory=list)
    password_updates: list[tuple[str, str]] = field(default_factory=list)
    chat_deleting_user_ids: list[str] = field(default_factory=list)

    def create_user(
        self,
        user_id: str,
        user_name: str,
        password_hash: str,
        created_at: datetime,
    ) -> AccountUserRecord:
        user = AccountUserRecord(
            user_id=user_id,
            user_name=user_name,
            password_hash=password_hash,
            created_at=created_at,
            updated_at=created_at,
        )
        self.users[user_id] = user
        self.created_users.append(user)
        return user

    def get_user_for_login(self, user_id: str) -> AccountUserRecord | None:
        return self.users.get(user_id)

    def find_user_by_id(self, user_id: str) -> AccountUserRecord | None:
        return self.users.get(user_id)

    def find_user_by_name(self, user_name: str) -> AccountUserRecord | None:
        for user in self.users.values():
            if user.user_name == user_name:
                return user
        return None

    def save_user(self, user: AccountUserData) -> None:
        self.users[user.user_id] = AccountUserRecord(
            user_id=user.user_id,
            user_name=user.user_name,
            password_hash=user.password_hash,
            user_state=user.user_state,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def update_user_name(
        self,
        user_id: str,
        user_name: str,
        updated_at: datetime,
    ) -> AccountUserRecord | None:
        user = self.users.get(user_id)
        if user is None or user.user_state != "active":
            return None
        updated = AccountUserRecord(
            user_id=user.user_id,
            user_name=user_name,
            password_hash=user.password_hash,
            user_state=user.user_state,
            created_at=user.created_at,
            updated_at=updated_at,
        )
        self.users[user_id] = updated
        return updated

    def update_password_hash(
        self,
        user_id: str,
        password_hash: str,
        updated_at: datetime,
    ) -> None:
        user = self.users[user_id]
        self.password_updates.append((user_id, password_hash))
        self.users[user_id] = AccountUserRecord(
            user_id=user.user_id,
            user_name=user.user_name,
            password_hash=password_hash,
            user_state=user.user_state,
            created_at=user.created_at,
            updated_at=updated_at,
        )

    def create_login_session(
        self,
        token_hash: str,
        user_id: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> LoginSessionRecord:
        user = self.users[user_id]
        session = LoginSessionRecord(
            session_row_id=len(self.sessions) + 1,
            token_hash=token_hash,
            user_id=user_id,
            user_name=user.user_name,
            user_state=user.user_state,
            expires_at=expires_at,
        )
        self.sessions[token_hash] = session
        self.created_sessions.append(session)
        return session

    def find_session_by_token_hash(
        self,
        token_hash: str,
    ) -> LoginSessionRecord | None:
        return self.sessions.get(token_hash)

    def find_valid_session(
        self,
        token_hash: str,
    ) -> LoginSessionRecord | None:
        return self.sessions.get(token_hash)

    def delete_session_by_token_hash(self, token_hash: str) -> int:
        self.deleted_session_hashes.append(token_hash)
        if token_hash in self.sessions:
            del self.sessions[token_hash]
            return 1
        return 0

    def delete_session(self, token_hash: str) -> None:
        self.delete_session_by_token_hash(token_hash)

    def delete_sessions_by_user_id(self, user_id: str) -> int:
        self.deleted_session_user_ids.append(user_id)
        matching_hashes = tuple(
            token_hash
            for token_hash, session in self.sessions.items()
            if session.user_id == user_id
        )
        for token_hash in matching_hashes:
            del self.sessions[token_hash]
        return len(matching_hashes)

    def mark_user_deleting(
        self,
        user_id: str,
        updated_at: datetime,
    ) -> str | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        self.users[user_id] = AccountUserRecord(
            user_id=user.user_id,
            user_name=user.user_name,
            password_hash=user.password_hash,
            user_state="deleting",
            created_at=user.created_at,
            updated_at=updated_at,
        )
        return "deleting"

    def mark_user_chats_deleting(self, user_id: str, updated_at: datetime) -> int:
        self.chat_deleting_user_ids.append(user_id)
        if updated_at.tzinfo is None:
            return 0
        return 1

    def delete_user(self, user_id: str) -> None:
        self.users.pop(user_id, None)


@dataclass(slots=True)
class FakeAccountDeletionDispatcher:
    next_result: DispatchResultRecord = field(
        default_factory=lambda: DispatchResultRecord(status="registered"),
    )
    dispatched: list[tuple[str, str]] = field(default_factory=list)

    def dispatch_account_deletion(
        self,
        user_id: str,
        trace_id: str,
    ) -> AccountDeletionDispatchResult:
        self.dispatched.append((user_id, trace_id))
        return AccountDeletionDispatchResult(
            status=self.next_result.status,
            diagnostic_message=self.next_result.diagnostic_message,
        )


@dataclass(slots=True)
class FakeTraceLogger:
    events: list[TraceEventRecord] = field(default_factory=list)

    def write_account_event(
        self,
        event_name: str,
        user_id: str,
        trace_id: str,
        diagnostic_message: str,
    ) -> None:
        self.events.append(
            TraceEventRecord(
                event_name=event_name,
                user_id=user_id,
                trace_id=trace_id,
                diagnostic_message=diagnostic_message,
            ),
        )

    def write(self, record: TraceLogRecord) -> Path:
        user_id = record.user_id if record.user_id is not None else ""
        self.events.append(
            TraceEventRecord(
                event_name=record.event_name,
                user_id=user_id,
                trace_id=str(record.trace_id),
                diagnostic_message=record.message,
            ),
        )
        return Path("/tmp/fake-trace-log.yaml")

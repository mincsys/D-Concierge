from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import NotRequired, TypedDict
from uuid import UUID

from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.engine import Engine

from backend.application.account.errors import FieldValidationError
from backend.application.ports.database.dto import (
    AcceptedRun,
    AnswerBlockData,
    AnswerData,
    ChatDetail,
    ChatRunData,
    DisplayReferenceData,
    HistoryItem,
    IntermediateMessageData,
)
from backend.application.ports.runtime.interface import RunDispatchResult
from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

FIXED_CHAT_NOW = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
F003_USER_ID = "user-001"
OTHER_USER_ID = "user-002"
CHAT_ID_VALUE = UUID("11111111-1111-7111-8111-111111111111")
RUN_ID_VALUE = UUID("22222222-2222-7222-8222-222222222222")
NEXT_RUN_ID_VALUE = UUID("33333333-3333-7333-8333-333333333333")
SESSION_ID_VALUE = UUID("44444444-4444-7444-8444-444444444444")
TRACE_ID_VALUE = "018fe2d4-0000-7000-8000-000000000003"


class PdfLocatorPayload(TypedDict):
    page_start: int
    page_end: int


class PdfLocatorDbPayload(PdfLocatorPayload):
    path: str


class ErrorPayload(TypedDict):
    error: str
    message: str


class FieldErrorPayload(ErrorPayload):
    field_errors: dict[str, str]


class ChatAcceptedPayload(TypedDict):
    chat_id: str
    run_id: str
    sse_url: str
    state: str


class ChatHistoryPayload(TypedDict):
    chat_id: str
    title: str
    latest_run_id: NotRequired[str]
    latest_state: str
    updated_at: str


class IntermediateMessagePayload(TypedDict):
    text: str


class DisplayReferencePayload(TypedDict):
    source_type: str
    label: str
    url: str
    locator: PdfLocatorPayload


class AnswerBlockPayload(TypedDict):
    markdown: str
    references: NotRequired[list[DisplayReferencePayload]]


class AnswerPayload(TypedDict):
    blocks: list[AnswerBlockPayload]


class ChatRunPayload(TypedDict):
    run_id: str
    state: str
    user_instruction: str
    intermediate_messages: NotRequired[list[IntermediateMessagePayload]]
    answer: NotRequired[AnswerPayload]
    user_message: NotRequired[str]


class ChatDetailPayload(TypedDict):
    chat_id: str
    title: str
    runs: list[ChatRunPayload]


@dataclass(frozen=True, slots=True)
class AcceptedRunRecord:
    chat_id: UUID
    run_id: UUID
    user_id: str
    session_id: UUID
    state: str = RunState.ACCEPTED.value
    started_at: datetime = FIXED_CHAT_NOW


@dataclass(frozen=True, slots=True)
class SavedFirstRunRecord:
    user_id: str
    chat_id: UUID
    run_id: UUID
    session_id: UUID
    title: str
    user_instruction: str
    trace_id: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class SavedAppendRunRecord:
    user_id: str
    chat_id: UUID
    run_id: UUID
    user_instruction: str
    trace_id: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class RunErrorRecord:
    run_id: UUID
    diagnostic_message: str


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    chat_id: UUID
    title: str
    latest_run_id: UUID | None
    latest_state: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IntermediateMessageRecord:
    text: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReferenceRecord:
    source_type: str
    label: str
    url: str
    locator: PdfLocatorPayload
    position: int


@dataclass(frozen=True, slots=True)
class AnswerBlockRecord:
    markdown: str
    position: int
    references: tuple[ReferenceRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class ChatRunRecord:
    run_id: UUID
    state: str
    user_instruction: str
    started_at: datetime
    intermediate_messages: tuple[IntermediateMessageRecord, ...] = ()
    answer_blocks: tuple[AnswerBlockRecord, ...] = ()
    user_message: str | None = None


@dataclass(frozen=True, slots=True)
class ChatDetailRecord:
    chat_id: UUID
    title: str
    chat_state: str
    runs: tuple[ChatRunRecord, ...]


@dataclass(frozen=True, slots=True)
class SeededChatUser:
    user_id: str
    user_name: str
    session_token: str
    session_token_hash: str


@dataclass(frozen=True, slots=True)
class SeededChatRun:
    chat_id: UUID
    run_id: UUID
    session_id: UUID
    instruction_id: UUID


DispatchResultRecord = RunDispatchResult


@dataclass(slots=True)
class FixedClock:
    now: datetime = FIXED_CHAT_NOW

    def now_utc(self) -> datetime:
        return self.now

    def now_app_timezone(self) -> datetime:
        return self.now


@dataclass(slots=True)
class FixedUuidGenerator:
    values: list[UUID] = field(
        default_factory=lambda: [
            CHAT_ID_VALUE,
            RUN_ID_VALUE,
            SESSION_ID_VALUE,
            NEXT_RUN_ID_VALUE,
        ],
    )

    def new_uuid(self) -> UUID:
        if not self.values:
            raise RuntimeError("固定UUIDを使い切りました。")
        return self.values.pop(0)


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
class FakeRunExecutionDispatcher:
    next_result: RunDispatchResult = field(
        default_factory=lambda: RunDispatchResult(status="registered"),
    )
    registrations: list[tuple[UUID, UUID, str]] = field(default_factory=list)

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> RunDispatchResult:
        self.registrations.append((chat_id, run_id, trace_id))
        return self.next_result


@dataclass(slots=True)
class FakeChatRepository:
    histories: dict[str, tuple[HistoryRecord, ...]] = field(default_factory=dict)
    details: dict[tuple[str, UUID], ChatDetailRecord] = field(default_factory=dict)
    conflict_chat_ids: set[UUID] = field(default_factory=set)
    deleting_chat_ids: set[UUID] = field(default_factory=set)
    saved_first_runs: list[SavedFirstRunRecord] = field(default_factory=list)
    saved_append_runs: list[SavedAppendRunRecord] = field(default_factory=list)
    run_errors: list[RunErrorRecord] = field(default_factory=list)

    def create_chat_with_first_run(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
        session_id: UUID,
        title: str,
        user_instruction: str,
        trace_id: str,
        started_at: datetime,
    ) -> AcceptedRun:
        record = SavedFirstRunRecord(
            user_id=user_id,
            chat_id=chat_id,
            run_id=run_id,
            session_id=session_id,
            title=title,
            user_instruction=user_instruction,
            trace_id=trace_id,
            started_at=started_at,
        )
        self.saved_first_runs.append(record)
        return AcceptedRun(
            chat_id=chat_id,
            run_id=run_id,
            user_id=user_id,
            session_id=session_id,
            state=RunState.ACCEPTED.value,
            started_at=started_at,
        )

    def append_run(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        trace_id: str,
        started_at: datetime,
    ) -> AcceptedRun:
        detail = self.details.get((user_id, chat_id))
        if detail is None:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="対象チャットが見つかりません。",
            )
        if (
            detail.chat_state == ChatState.DELETING.value
            or chat_id in self.deleting_chat_ids
        ):
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        if chat_id in self.conflict_chat_ids:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="未完了のチャット実行処理があります。",
            )
        self.saved_append_runs.append(
            SavedAppendRunRecord(
                user_id=user_id,
                chat_id=chat_id,
                run_id=run_id,
                user_instruction=user_instruction,
                trace_id=trace_id,
                started_at=started_at,
            )
        )
        return AcceptedRun(
            chat_id=chat_id,
            run_id=run_id,
            user_id=user_id,
            session_id=SESSION_ID_VALUE,
            state=RunState.ACCEPTED.value,
            started_at=started_at,
        )

    def mark_run_error(self, run_id: UUID, diagnostic_message: str) -> None:
        self.run_errors.append(
            RunErrorRecord(
                run_id=run_id,
                diagnostic_message=diagnostic_message,
            )
        )

    def list_histories(self, user_id: str) -> tuple[HistoryItem, ...]:
        return tuple(
            HistoryItem(
                chat_id=history.chat_id,
                title=history.title,
                latest_run_id=history.latest_run_id,
                latest_state=history.latest_state,
                updated_at=history.updated_at,
            )
            for history in self.histories.get(user_id, ())
        )

    def get_chat_detail(self, user_id: str, chat_id: UUID) -> ChatDetail | None:
        detail = self.details.get((user_id, chat_id))
        if detail is not None and detail.chat_state == ChatState.DELETING.value:
            raise AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            )
        if detail is None:
            return None
        return _to_port_chat_detail(detail)


def assert_validation_field(error: FieldValidationError, field_name: str) -> None:
    assert field_name in error.field_errors


def fixed_history_records() -> tuple[HistoryRecord, ...]:
    return (
        HistoryRecord(
            chat_id=UUID("55555555-5555-7555-8555-555555555555"),
            title="新しい履歴",
            latest_run_id=UUID("66666666-6666-7666-8666-666666666666"),
            latest_state=RunState.COMPLETED.value,
            updated_at=FIXED_CHAT_NOW + timedelta(minutes=2),
        ),
        HistoryRecord(
            chat_id=CHAT_ID_VALUE,
            title="受付中の履歴",
            latest_run_id=RUN_ID_VALUE,
            latest_state=RunState.ACCEPTED.value,
            updated_at=FIXED_CHAT_NOW,
        ),
    )


def fixed_chat_detail_record() -> ChatDetailRecord:
    return ChatDetailRecord(
        chat_id=CHAT_ID_VALUE,
        title="履歴タイトル",
        chat_state=ChatState.ACTIVE.value,
        runs=(
            ChatRunRecord(
                run_id=RUN_ID_VALUE,
                state=RunState.COMPLETED.value,
                user_instruction="最初の指示",
                started_at=FIXED_CHAT_NOW,
                intermediate_messages=(
                    IntermediateMessageRecord(
                        text="作業を開始します。",
                        created_at=FIXED_CHAT_NOW,
                    ),
                ),
                answer_blocks=(
                    AnswerBlockRecord(
                        markdown="回答本文",
                        position=1,
                        references=(
                            ReferenceRecord(
                                source_type="pdf",
                                label="資料A",
                                url="/api/references/77777777-7777-7777-8777-777777777777",
                                locator={
                                    "page_start": 2,
                                    "page_end": 3,
                                },
                                position=1,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _to_port_chat_detail(detail: ChatDetailRecord) -> ChatDetail:
    return ChatDetail(
        chat_id=detail.chat_id,
        title=detail.title,
        runs=tuple(_to_port_chat_run(run) for run in detail.runs),
    )


def _to_port_chat_run(run: ChatRunRecord) -> ChatRunData:
    answer = None
    if run.answer_blocks:
        answer = AnswerData(
            blocks=tuple(
                AnswerBlockData(
                    answer_block_id=UUID("aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa"),
                    position=block.position,
                    markdown=block.markdown,
                    references=tuple(
                        DisplayReferenceData(
                            reference_id=UUID(
                                reference.url.rsplit("/", maxsplit=1)[-1],
                            ),
                            position=reference.position,
                            source_type=reference.source_type,
                            label=reference.label,
                            path=reference.url,
                            page_start=reference.locator["page_start"],
                            page_end=reference.locator["page_end"],
                        )
                        for reference in block.references
                    ),
                    artifacts=(),
                )
                for block in run.answer_blocks
            ),
        )
    return ChatRunData(
        run_id=run.run_id,
        state=run.state,
        user_instruction=run.user_instruction,
        started_at=run.started_at,
        intermediate_messages=tuple(
            IntermediateMessageData(
                text=message.text,
                created_at=message.created_at,
            )
            for message in run.intermediate_messages
        ),
        answer=answer,
        user_message=run.user_message,
    )


def seed_chat_user(
    database_url: str,
    *,
    user_id: str = F003_USER_ID,
    user_name: str = "利用者",
    session_token: str = "f003-session-token",
    user_state: str = "active",
) -> SeededChatUser:
    from backend.infrastructure.security.password_hasher import PasslibPasswordHasher
    from backend.infrastructure.security.session_token import (
        SecretsSessionTokenProvider,
    )

    password_hash = PasslibPasswordHasher().hash_password("current-password")
    session_token_hash = SecretsSessionTokenProvider().hash_token(session_token)
    engine = create_engine(database_url)
    try:
        users = metadata_table(engine, "users")
        login_sessions = metadata_table(engine, "login_sessions")
        with engine.begin() as connection:
            connection.execute(
                users.insert().values(
                    id=user_id,
                    user_name=user_name,
                    password_hash=password_hash,
                    user_state=user_state,
                    created_at=FIXED_CHAT_NOW,
                    updated_at=FIXED_CHAT_NOW,
                ),
            )
            connection.execute(
                login_sessions.insert().values(
                    token_hash=session_token_hash,
                    user_id=user_id,
                    expires_at=FIXED_CHAT_NOW + timedelta(days=400),
                    created_at=FIXED_CHAT_NOW,
                    updated_at=FIXED_CHAT_NOW,
                ),
            )
    finally:
        engine.dispose()
    return SeededChatUser(
        user_id=user_id,
        user_name=user_name,
        session_token=session_token,
        session_token_hash=session_token_hash,
    )


def insert_chat_run(
    database_url: str,
    *,
    user_id: str,
    chat_id: UUID,
    run_id: UUID,
    session_id: UUID,
    instruction_id: UUID,
    title: str,
    instruction: str,
    run_state: str,
    chat_state: str = ChatState.ACTIVE.value,
    updated_at: datetime = FIXED_CHAT_NOW,
    started_at: datetime = FIXED_CHAT_NOW,
    user_message: str | None = None,
) -> SeededChatRun:
    engine = create_engine(database_url)
    try:
        chats = metadata_table(engine, "chats")
        chat_runs = metadata_table(engine, "chat_runs")
        user_instructions = metadata_table(engine, "user_instructions")
        with engine.begin() as connection:
            connection.execute(
                chats.insert().values(
                    id=chat_id,
                    user_id=user_id,
                    session_id=session_id,
                    chat_state=chat_state,
                    title=title,
                    generation_conversation_id=None,
                    validation_conversation_id=None,
                    updated_at=updated_at,
                ),
            )
            connection.execute(
                chat_runs.insert().values(
                    id=run_id,
                    chat_id=chat_id,
                    state=run_state,
                    started_at=started_at,
                    execution_deadline_at=None,
                    ended_at=None,
                    user_message=user_message,
                ),
            )
            connection.execute(
                user_instructions.insert().values(
                    id=instruction_id,
                    run_id=run_id,
                    body=instruction,
                ),
            )
    finally:
        engine.dispose()
    return SeededChatRun(
        chat_id=chat_id,
        run_id=run_id,
        session_id=session_id,
        instruction_id=instruction_id,
    )


def insert_completed_answer(
    database_url: str,
    *,
    run_id: UUID,
    message_id: UUID,
    answer_block_id: UUID,
    reference_id: UUID,
) -> None:
    engine = create_engine(database_url)
    try:
        intermediate_messages = metadata_table(engine, "intermediate_messages")
        answer_blocks = metadata_table(engine, "answer_blocks")
        references = metadata_table(engine, "references")
        with engine.begin() as connection:
            connection.execute(
                intermediate_messages.insert().values(
                    id=message_id,
                    run_id=run_id,
                    body="作業を開始します。",
                    created_at=FIXED_CHAT_NOW,
                ),
            )
            connection.execute(
                answer_blocks.insert().values(
                    id=answer_block_id,
                    run_id=run_id,
                    position=1,
                    markdown="回答本文",
                ),
            )
            locator: PdfLocatorDbPayload = {
                "path": "manual/a.pdf",
                "page_start": 2,
                "page_end": 3,
            }
            connection.execute(
                references.insert().values(
                    id=reference_id,
                    answer_block_id=answer_block_id,
                    position=1,
                    source_type="pdf",
                    label="資料A",
                    locator=locator,
                ),
            )
    finally:
        engine.dispose()


def metadata_table(engine: Engine, table_name: str) -> Table:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=(table_name,))
    return metadata.tables[table_name]


def table_count(database_url: str, table_name: str) -> int:
    engine = create_engine(database_url)
    try:
        table = metadata_table(engine, table_name)
        with engine.connect() as connection:
            count_value = connection.scalar(select(func.count()).select_from(table))
    finally:
        engine.dispose()
    assert isinstance(count_value, int)
    return count_value


def run_state(database_url: str, run_id: UUID) -> str | None:
    engine = create_engine(database_url)
    try:
        chat_runs = metadata_table(engine, "chat_runs")
        with engine.connect() as connection:
            state = connection.scalar(
                select(chat_runs.c.state).where(chat_runs.c.id == run_id),
            )
    finally:
        engine.dispose()
    assert isinstance(state, str) or state is None
    return state


def run_states(database_url: str) -> tuple[str, ...]:
    engine = create_engine(database_url)
    try:
        chat_runs = metadata_table(engine, "chat_runs")
        with engine.connect() as connection:
            rows = connection.execute(
                select(chat_runs.c.state).order_by(chat_runs.c.id),
            )
    finally:
        engine.dispose()
    return tuple(str(row[0]) for row in rows)


def instruction_bodies(database_url: str) -> tuple[str, ...]:
    engine = create_engine(database_url)
    try:
        user_instructions = metadata_table(engine, "user_instructions")
        with engine.connect() as connection:
            rows = connection.execute(
                select(user_instructions.c.body).order_by(user_instructions.c.body),
            )
    finally:
        engine.dispose()
    return tuple(str(row[0]) for row in rows)

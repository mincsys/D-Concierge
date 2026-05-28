from datetime import UTC, datetime
from sqlite3 import Connection as SQLiteConnection
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from backend.application.ports.database.dto import (
    SHARED_LOCAL_USER_ID,
    AcceptedRun,
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    ChatDeletionTarget,
    ChatDetail,
    ChatRuntimeContext,
    DeleteChatResult,
    DisplayReferenceData,
    HistoryItem,
    UnfinishedRun,
)
from backend.application.ports.runtime.interface import ClockPort
from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.domain.references.source_type import SourceType
from backend.infrastructure.database.models.answer import (
    AnswerBlockModel,
    ReferenceModel,
)
from backend.infrastructure.database.models.base import Base
from backend.infrastructure.database.models.chat import (
    ChatModel,
    ChatRunModel,
    LocalUserModel,
    UserInstructionModel,
    UserModel,
)
from backend.infrastructure.database.repositories.sqlalchemy_chat_repository import (
    SqlAlchemyChatRepository,
)
from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


def test_sqlalchemy_repository_persists_chat_run_and_detail() -> None:
    """観点：チャットRepository IF。

    確認：チャット、run、指示を保存し、詳細取得できる。
    """
    repository = _make_repository()

    accepted = repository.create_chat_with_first_run(" 初回指示 ")
    detail = repository.get_chat_detail(accepted.chat_id)

    assert detail.chat_id == accepted.chat_id
    assert detail.title == "初回指示"
    assert detail.runs[0].run_id == accepted.run_id
    assert detail.runs[0].state is RunState.ACCEPTED
    assert detail.runs[0].user_instruction == "初回指示"


def test_sqlalchemy_repository_rejects_append_when_unfinished_run_exists() -> None:
    """観点：チャットRepository IF。確認：未完了runがある場合は継続指示を競合にする。"""
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("初回")

    try:
        repository.append_run(accepted.chat_id, "追加")
    except AppError as exc:
        assert exc.error_type is ErrorType.CONFLICT
    else:
        raise AssertionError("未完了runの競合が発生しませんでした。")


def test_sqlalchemy_repository_lists_histories_by_updated_desc() -> None:
    """観点：履歴一覧取得。確認：更新日時降順で最新run状態を返す。"""
    repository = _make_repository(
        clock=SequenceClock(
            (
                datetime(2026, 5, 9, 10, 0, 0, tzinfo=UTC),
                datetime(2026, 5, 9, 10, 0, 1, tzinfo=UTC),
            )
        )
    )
    first = repository.create_chat_with_first_run("古い履歴")
    second = repository.create_chat_with_first_run("新しい履歴")

    histories = repository.list_histories()

    assert [item.chat_id for item in histories] == [second.chat_id, first.chat_id]
    assert histories[0].latest_state is RunState.ACCEPTED


def test_sqlalchemy_repository_filters_chat_data_by_account_user() -> None:
    """観点：ユーザ単位の履歴分離。

    確認：アカウントユーザIDを指定したチャットは、別ユーザの履歴・詳細・削除対象にならない。
    """
    repository, session_factory = _make_repository_with_session_factory()
    _insert_user(session_factory, "demo-user")
    _insert_user(session_factory, "other-user")

    own = repository.create_chat_with_first_run("自分の履歴", user_id="demo-user")
    other = repository.create_chat_with_first_run("他人の履歴", user_id="other-user")

    histories = repository.list_histories(user_id="demo-user")
    assert [history.chat_id for history in histories] == [own.chat_id]
    assert repository.get_chat_detail(own.chat_id, user_id="demo-user").title == (
        "自分の履歴"
    )

    with pytest.raises(AppError) as detail_error:
        repository.get_chat_detail(other.chat_id, user_id="demo-user")
    assert detail_error.value.error_type is ErrorType.NOT_FOUND

    with pytest.raises(AppError) as delete_error:
        repository.mark_chat_deleting(other.chat_id, user_id="demo-user")
    assert delete_error.value.error_type is ErrorType.NOT_FOUND


def test_sqlalchemy_repository_marks_and_deletes_account_user_chats() -> None:
    """観点：アカウント削除処理。

    確認：対象ユーザのチャットだけを削除中にし、アカウント物理削除でDBから削除する。
    """
    repository, session_factory = _make_repository_with_session_factory()
    _insert_user(session_factory, "demo-user")
    _insert_user(session_factory, "other-user")
    own = repository.create_chat_with_first_run("削除対象", user_id="demo-user")
    other = repository.create_chat_with_first_run("保持対象", user_id="other-user")

    with repository._transaction_manager.transaction():
        repository.mark_user_chats_deleting(
            "demo-user", datetime(2026, 5, 9, 10, 0, tzinfo=UTC)
        )

    with session_factory() as session:
        own_chat = session.get(ChatModel, own.chat_id)
        other_chat = session.get(ChatModel, other.chat_id)
        assert own_chat is not None
        assert other_chat is not None
        assert own_chat.chat_state == ChatState.DELETING.value
        assert other_chat.chat_state == ChatState.ACTIVE.value

    with repository._transaction_manager.transaction():
        target = repository.get_account_deletion_target("demo-user")
        repository.delete_account_data("demo-user")

    assert target is not None
    assert target.user_id == "demo-user"
    assert repository.list_histories(user_id="demo-user") == ()
    assert [
        history.chat_id for history in repository.list_histories(user_id="other-user")
    ] == [other.chat_id]


def test_sqlalchemy_repository_persists_execution_result_for_detail() -> None:
    """観点：チャット実行Repository IF。

    確認：状態、中間メッセージ、回答、参照元、成果物を保存し、詳細再表示できる。
    """
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    reference_id = UUID("00000000-0000-0000-0000-000000000101")
    artifact_id = UUID("00000000-0000-0000-0000-000000000102")

    assert (
        repository.get_run_instruction(accepted.chat_id, accepted.run_id)
        == "資料を要約"
    )
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.RUNNING)
    repository.add_intermediate_message(
        accepted.chat_id, accepted.run_id, "資料を検索しています。"
    )
    repository.save_completed_answer(
        accepted.chat_id,
        accepted.run_id,
        AnswerData(
            blocks=(
                AnswerBlockData(
                    markdown="検証済み回答",
                    references=(
                        DisplayReferenceData(
                            reference_id=reference_id,
                            source_type=SourceType.PDF,
                            label="資料",
                            relative_path="manual.pdf",
                            page_start=2,
                            page_end=3,
                        ),
                    ),
                    artifacts=(
                        ArtifactData(
                            artifact_id=artifact_id,
                            mime_type="image/svg+xml",
                            relative_path="chart.svg",
                        ),
                    ),
                ),
            ),
        ),
    )
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.COMPLETED)

    detail = repository.get_chat_detail(accepted.chat_id)

    assert (
        repository.get_run_state(accepted.chat_id, accepted.run_id)
        is RunState.COMPLETED
    )
    assert detail.runs[0].state is RunState.COMPLETED
    assert detail.runs[0].intermediate_messages[0].text == "資料を検索しています。"
    assert detail.runs[0].answer is not None
    assert detail.runs[0].answer.blocks[0].markdown == "検証済み回答"
    assert detail.runs[0].answer.blocks[0].references[0].relative_path == "manual.pdf"
    assert detail.runs[0].answer.blocks[0].artifacts[0].relative_path == "chart.svg"
    assert repository.get_reference(reference_id).page_start == 2
    assert repository.get_artifact(artifact_id).mime_type == "image/svg+xml"


def test_sqlalchemy_repository_saves_answer_with_foreign_key_checks() -> None:
    """観点：回答保存順序。

    確認：DBの外部キー制約が有効でも、回答、回答ブロック、参照元を親から順に保存できる。
    """
    repository = _make_repository_with_foreign_key_checks()
    accepted = repository.create_chat_with_first_run("資料を要約")
    reference_id = UUID("00000000-0000-0000-0000-000000000111")

    repository.save_completed_answer(
        accepted.chat_id,
        accepted.run_id,
        AnswerData(
            blocks=(
                AnswerBlockData(
                    markdown="検証済み回答",
                    references=(
                        DisplayReferenceData(
                            reference_id=reference_id,
                            source_type=SourceType.PDF,
                            label="資料",
                            relative_path="manual.pdf",
                            page_start=2,
                            page_end=3,
                        ),
                    ),
                ),
            ),
        ),
    )

    detail = repository.get_chat_detail(accepted.chat_id)

    assert detail.runs[0].answer is not None
    assert detail.runs[0].answer.blocks[0].references[0].reference_id == reference_id


def test_sqlalchemy_repository_schema_uses_answer_blocks_without_answers_table() -> (
    None
):
    """観点：物理データ構造。確認：回答ブロックをrunへ直接紐づけ、回答テーブルを持たない。"""
    assert "answers" not in Base.metadata.tables
    assert "run_id" in AnswerBlockModel.__table__.columns
    assert "answer_id" not in AnswerBlockModel.__table__.columns


def test_sqlalchemy_repository_allows_append_after_terminal_run() -> None:
    """観点：継続指示Repository IF。

    確認：終端runだけのチャットには継続runを追加できる。
    """
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.COMPLETED)

    appended = repository.append_run(accepted.chat_id, "追加")

    assert appended.chat_id == accepted.chat_id
    assert appended.state is RunState.ACCEPTED


def test_sqlalchemy_repository_rejects_cancel_for_terminal_run() -> None:
    """観点：キャンセルRepository IF。確認：終端済みrunのキャンセルを競合にする。"""
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("初回")
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.COMPLETED)

    try:
        repository.cancel_run(accepted.chat_id, accepted.run_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.CONFLICT
    else:
        raise AssertionError("終端済みrunのキャンセル競合が発生しませんでした。")


def test_sqlalchemy_repository_cancels_accepted_run() -> None:
    """観点：キャンセルRepository IF。確認：受付runをキャンセル済みへ更新する。"""
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("初回")

    repository.cancel_run(accepted.chat_id, accepted.run_id)

    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state is RunState.CANCELED
    assert detail.runs[0].user_message == "処理をキャンセルしました。"


def test_sqlalchemy_repository_updates_state_conditionally_and_saves_deadline() -> None:
    """観点：状態条件付き更新。

    確認：期待状態に一致する場合だけ状態とexecution_deadline_atを更新する。
    """
    repository, session_factory = _make_repository_with_session_factory()
    accepted = repository.create_chat_with_first_run("初回")
    deadline = datetime(2026, 5, 9, 10, 5, tzinfo=UTC)

    updated = repository.update_run_state_if_current(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        expected_states=(RunState.ACCEPTED,),
        state=RunState.RUNNING,
        execution_deadline_at=deadline,
    )
    stale = repository.update_run_state_if_current(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        expected_states=(RunState.ACCEPTED,),
        state=RunState.ERROR,
    )

    with session_factory() as session:
        run = session.get(ChatRunModel, accepted.run_id)

    assert updated is True
    assert stale is False
    assert run is not None
    assert run.state == RunState.RUNNING.value
    assert run.execution_deadline_at is not None
    assert run.execution_deadline_at.replace(tzinfo=UTC) == deadline


def test_sqlalchemy_repository_rejects_missing_records() -> None:
    """観点：Repository IF異常系。確認：対象なしをNOT_FOUNDへ変換する。"""
    repository = _make_repository()
    missing_chat_id = uuid4()
    missing_run_id = uuid4()

    try:
        repository.get_chat_detail(missing_chat_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.NOT_FOUND
    else:
        raise AssertionError("対象なしチャットの例外が発生しませんでした。")

    accepted = repository.create_chat_with_first_run("初回")
    try:
        repository.get_run_state(accepted.chat_id, missing_run_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.NOT_FOUND
    else:
        raise AssertionError("対象なしrunの例外が発生しませんでした。")


def test_sqlalchemy_repository_lists_unfinished_runs_for_recovery() -> None:
    """観点：起動時回復Repository IF。確認：未完了runだけを回復対象として取得する。"""
    repository = _make_repository(
        clock=SequenceClock(
            (
                datetime(2026, 5, 9, 10, 0, 0, tzinfo=UTC),
                datetime(2026, 5, 9, 10, 0, 1, tzinfo=UTC),
                datetime(2026, 5, 9, 10, 0, 2, tzinfo=UTC),
                datetime(2026, 5, 9, 10, 0, 3, tzinfo=UTC),
            )
        )
    )
    accepted = repository.create_chat_with_first_run("accepted run")
    running = repository.create_chat_with_first_run("running run")
    canceling = repository.create_chat_with_first_run("cancel requested run")
    terminal = repository.create_chat_with_first_run("completed run")
    repository.set_run_state(running.chat_id, running.run_id, RunState.RUNNING)
    repository.set_run_state(
        canceling.chat_id,
        canceling.run_id,
        RunState.CANCEL_REQUESTED,
    )
    repository.set_run_state(terminal.chat_id, terminal.run_id, RunState.COMPLETED)

    unfinished = repository.list_unfinished_runs_for_recovery()

    assert [(run.chat_id, run.run_id, run.state) for run in unfinished] == [
        (accepted.chat_id, accepted.run_id, RunState.ACCEPTED),
        (running.chat_id, running.run_id, RunState.RUNNING),
        (canceling.chat_id, canceling.run_id, RunState.CANCEL_REQUESTED),
    ]


def test_sqlalchemy_repository_saves_and_loads_codex_runtime_context() -> None:
    """観点：チャットRepository IF。

    確認：作業領域IDとCodex側resume IDを保存取得できる。
    """
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("資料を要約")

    initial_context = repository.get_chat_runtime_context(accepted.chat_id)
    repository.save_generation_conversation_id(accepted.chat_id, "gen-thread")
    repository.save_validation_conversation_id(accepted.chat_id, "val-thread")
    saved_context = repository.get_chat_runtime_context(accepted.chat_id)

    assert initial_context.local_user_id == SHARED_LOCAL_USER_ID
    assert initial_context.session_id != accepted.chat_id
    assert initial_context.session_id != accepted.run_id
    assert initial_context.generation_conversation_id is None
    assert initial_context.validation_conversation_id is None
    assert saved_context.session_id == initial_context.session_id
    assert saved_context.generation_conversation_id == "gen-thread"
    assert saved_context.validation_conversation_id == "val-thread"


def test_sqlalchemy_repository_rejects_missing_reference_and_artifact() -> None:
    """観点：配信メタ情報Repository IF。

    確認：未保存の参照元IDと成果物IDをNOT_FOUNDへ変換する。
    """
    repository = _make_repository()

    try:
        repository.get_reference(uuid4())
    except AppError as exc:
        assert exc.error_type is ErrorType.NOT_FOUND
    else:
        raise AssertionError("対象なし参照元の例外が発生しませんでした。")

    try:
        repository.get_artifact(uuid4())
    except AppError as exc:
        assert exc.error_type is ErrorType.NOT_FOUND
    else:
        raise AssertionError("対象なし成果物の例外が発生しませんでした。")


def test_sqlalchemy_repository_excludes_deleting_chat_and_returns_deletion_target() -> (
    None
):
    """観点：チャット削除Repository IF。

    確認：削除中チャットを履歴と詳細から除外し、物理削除対象情報を返す。
    """
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("削除対象")
    artifact_id = UUID("00000000-0000-0000-0000-000000000701")
    repository.save_completed_answer(
        accepted.chat_id,
        accepted.run_id,
        AnswerData(
            blocks=(
                AnswerBlockData(
                    markdown="回答",
                    artifacts=(
                        ArtifactData(
                            artifact_id=artifact_id,
                            mime_type="image/svg+xml",
                            relative_path="run-id/chart.svg",
                        ),
                    ),
                ),
            ),
        ),
    )

    deleted = repository.mark_chat_deleting(accepted.chat_id)
    target = repository.get_chat_deletion_target(accepted.chat_id)

    assert deleted.chat_state is ChatState.DELETING
    assert repository.list_histories() == ()
    assert target.artifact_storage_paths == ("run-id/chart.svg",)
    assert target.unfinished_runs[0].run_id == accepted.run_id
    try:
        repository.get_chat_detail(accepted.chat_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.CONFLICT
    else:
        raise AssertionError("削除中チャットの競合が発生しませんでした。")


def test_sqlalchemy_repository_delete_chat_cascade_removes_related_records() -> None:
    """観点：チャット削除Repository IF。

    確認：対象チャット一式をDBから削除する。
    """
    repository = _make_repository()
    accepted = repository.create_chat_with_first_run("削除対象")
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.COMPLETED)
    repository.mark_chat_deleting(accepted.chat_id)

    repository.delete_chat_cascade(accepted.chat_id)

    try:
        repository.get_chat_deletion_target(accepted.chat_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.NOT_FOUND
    else:
        raise AssertionError("削除後チャットの対象なしが発生しませんでした。")


def test_sqlalchemy_repository_rejects_blank_instruction() -> None:
    """観点：Repository IF入力検証。確認：空白だけの指示をINPUTとして拒否する。"""
    repository = _make_repository()

    try:
        repository.create_chat_with_first_run("   ")
    except AppError as exc:
        assert exc.error_type is ErrorType.INPUT
    else:
        raise AssertionError("空白指示の例外が発生しませんでした。")


def test_sqlalchemy_repository_rejects_corrupted_reference_locator() -> None:
    """観点：Repository IFデータ整合性。

    確認：参照元locatorが不正なDB内容をSYSTEMへ変換する。
    """
    repository, session_factory = _make_repository_with_session_factory()
    accepted = repository.create_chat_with_first_run("初回")
    reference_id = uuid4()
    with session_factory() as session:
        with session.begin():
            block_id = uuid4()
            session.add(
                AnswerBlockModel(
                    id=block_id,
                    run_id=accepted.run_id,
                    position=1,
                    markdown="回答",
                )
            )
            session.add(
                ReferenceModel(
                    id=reference_id,
                    answer_block_id=block_id,
                    position=1,
                    source_type=SourceType.PDF.value,
                    label="資料",
                    locator={"path": "manual.pdf"},
                )
            )

    try:
        repository.get_reference(reference_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.SYSTEM
    else:
        raise AssertionError("不正locatorの例外が発生しませんでした。")

    try:
        repository.get_chat_detail(accepted.chat_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.SYSTEM
    else:
        raise AssertionError("不正locator詳細取得の例外が発生しませんでした。")


def test_sqlalchemy_repository_rejects_run_without_instruction() -> None:
    """観点：Repository IFデータ整合性。

    確認：ユーザ指示を欠くrunをSYSTEMへ変換する。
    """
    repository, session_factory = _make_repository_with_session_factory()
    accepted = repository.create_chat_with_first_run("初回")
    with session_factory() as session:
        with session.begin():
            session.execute(
                sa.delete(UserInstructionModel).where(
                    UserInstructionModel.run_id == accepted.run_id
                )
            )

    try:
        repository.get_chat_detail(accepted.chat_id)
    except AppError as exc:
        assert exc.error_type is ErrorType.SYSTEM
    else:
        raise AssertionError("指示なしrunの例外が発生しませんでした。")


def test_sqlalchemy_repository_ignores_history_without_run() -> None:
    """観点：履歴一覧Repository IF。確認：runを持たないチャットを履歴一覧へ返さない。"""
    repository, session_factory = _make_repository_with_session_factory()
    with session_factory() as session:
        with session.begin():
            session.add(
                LocalUserModel(
                    id=SHARED_LOCAL_USER_ID,
                    display_name="共有利用者",
                    is_active=True,
                )
            )
            session.add(
                ChatModel(
                    id=uuid4(),
                    local_user_id=SHARED_LOCAL_USER_ID,
                    session_id=uuid4(),
                    title="runなし",
                    updated_at=datetime(2026, 5, 9, 10, 0, tzinfo=UTC),
                )
            )

    assert repository.list_histories() == ()


def _make_repository(
    clock: ClockPort | None = None,
) -> "TransactionalSqlAlchemyChatRepository":
    repository, _session_factory = _make_repository_with_session_factory(clock=clock)
    return repository


def _make_repository_with_session_factory(
    clock: ClockPort | None = None,
) -> tuple["TransactionalSqlAlchemyChatRepository", sessionmaker[Session]]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    transaction_manager = SqlAlchemyTransactionManager(session_factory=session_factory)
    return (
        TransactionalSqlAlchemyChatRepository(transaction_manager, clock=clock),
        session_factory,
    )


def _make_repository_with_foreign_key_checks() -> (
    "TransactionalSqlAlchemyChatRepository"
):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @sa.event.listens_for(engine, "connect")
    def _enable_foreign_keys(
        dbapi_connection: SQLiteConnection,
        _connection_record: ConnectionPoolEntry,
    ) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    transaction_manager = SqlAlchemyTransactionManager(session_factory=session_factory)
    return TransactionalSqlAlchemyChatRepository(transaction_manager)


def _insert_user(
    session_factory: sessionmaker[Session],
    user_id: str,
    user_name: str = "テストユーザ",
) -> None:
    with session_factory() as session:
        with session.begin():
            session.add(
                UserModel(
                    id=user_id,
                    user_name=user_name,
                    password_hash="hashed-password",
                    user_state="通常",
                    created_at=datetime(2026, 5, 9, 10, 0, tzinfo=UTC),
                    updated_at=datetime(2026, 5, 9, 10, 0, tzinfo=UTC),
                )
            )


class TransactionalSqlAlchemyChatRepository(SqlAlchemyChatRepository):
    """Repositoryテスト用に各呼び出しを明示トランザクションへ包む。"""

    def __init__(
        self,
        transaction_manager: SqlAlchemyTransactionManager,
        clock: ClockPort | None = None,
    ) -> None:
        super().__init__(session_provider=transaction_manager, clock=clock)
        self._transaction_manager = transaction_manager

    def create_chat_with_first_run(
        self, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
        with self._transaction_manager.transaction():
            return super().create_chat_with_first_run(user_instruction, user_id)

    def append_run(
        self, chat_id: UUID, user_instruction: str, user_id: str = ""
    ) -> AcceptedRun:
        with self._transaction_manager.transaction():
            return super().append_run(chat_id, user_instruction, user_id)

    def list_histories(self, user_id: str = "") -> tuple[HistoryItem, ...]:
        with self._transaction_manager.transaction():
            return super().list_histories(user_id)

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        with self._transaction_manager.transaction():
            return super().list_unfinished_runs_for_recovery()

    def get_chat_detail(self, chat_id: UUID, user_id: str = "") -> ChatDetail:
        with self._transaction_manager.transaction():
            return super().get_chat_detail(chat_id, user_id)

    def get_chat_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext:
        with self._transaction_manager.transaction():
            return super().get_chat_runtime_context(chat_id)

    def save_generation_conversation_id(
        self,
        chat_id: UUID,
        codex_conversation_id: str,
    ) -> None:
        with self._transaction_manager.transaction():
            super().save_generation_conversation_id(chat_id, codex_conversation_id)

    def save_validation_conversation_id(
        self,
        chat_id: UUID,
        codex_conversation_id: str,
    ) -> None:
        with self._transaction_manager.transaction():
            super().save_validation_conversation_id(chat_id, codex_conversation_id)

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        with self._transaction_manager.transaction():
            return super().get_run_state(chat_id, run_id)

    def get_run_instruction(self, chat_id: UUID, run_id: UUID) -> str:
        with self._transaction_manager.transaction():
            return super().get_run_instruction(chat_id, run_id)

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        with self._transaction_manager.transaction():
            super().set_run_state(chat_id, run_id, state, user_message)

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
        execution_deadline_at: datetime | None = None,
    ) -> bool:
        with self._transaction_manager.transaction():
            return super().update_run_state_if_current(
                chat_id,
                run_id,
                expected_states,
                state,
                user_message,
                execution_deadline_at,
            )

    def add_intermediate_message(self, chat_id: UUID, run_id: UUID, text: str) -> None:
        with self._transaction_manager.transaction():
            super().add_intermediate_message(chat_id, run_id, text)

    def save_completed_answer(
        self,
        chat_id: UUID,
        run_id: UUID,
        answer: AnswerData,
    ) -> None:
        with self._transaction_manager.transaction():
            super().save_completed_answer(chat_id, run_id, answer)

    def cancel_run(self, chat_id: UUID, run_id: UUID) -> None:
        with self._transaction_manager.transaction():
            super().cancel_run(chat_id, run_id)

    def get_reference(self, reference_id: UUID) -> DisplayReferenceData:
        with self._transaction_manager.transaction():
            return super().get_reference(reference_id)

    def get_artifact(self, artifact_id: UUID) -> ArtifactData:
        with self._transaction_manager.transaction():
            return super().get_artifact(artifact_id)

    def mark_chat_deleting(self, chat_id: UUID, user_id: str = "") -> DeleteChatResult:
        with self._transaction_manager.transaction():
            return super().mark_chat_deleting(chat_id, user_id)

    def list_deleting_chats_for_recovery(self) -> tuple[UUID, ...]:
        with self._transaction_manager.transaction():
            return super().list_deleting_chats_for_recovery()

    def get_chat_deletion_target(self, chat_id: UUID) -> ChatDeletionTarget:
        with self._transaction_manager.transaction():
            return super().get_chat_deletion_target(chat_id)

    def delete_chat_cascade(self, chat_id: UUID) -> None:
        with self._transaction_manager.transaction():
            super().delete_chat_cascade(chat_id)


class SequenceClock:
    """Repositoryテスト用に時刻を順番に返すClock。"""

    def __init__(self, values: tuple[datetime, ...]) -> None:
        self._values = list(values)

    def now(self) -> datetime:
        if self._values:
            return self._values.pop(0)
        return datetime(2026, 5, 9, 10, 0, tzinfo=UTC)

    def now_utc(self) -> datetime:
        return self.now()

    def now_app_timezone(self) -> datetime:
        return self.now()

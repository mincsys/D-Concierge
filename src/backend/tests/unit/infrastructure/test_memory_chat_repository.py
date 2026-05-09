from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.infrastructure.memory.repository import (
    SHARED_LOCAL_USER_ID,
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    DisplayReferenceData,
    InMemoryChatRepository,
)
from backend.shared.errors import AppError, ErrorClass


def test_memory_repository_saves_answer_references_and_artifacts() -> None:
    """観点：メモリRepository IF。

    確認：検証済み回答、参照元、成果物を保存し、配信メタ情報として取得できる。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    reference_id = UUID("00000000-0000-0000-0000-000000000201")
    artifact_id = UUID("00000000-0000-0000-0000-000000000202")

    repository.save_completed_answer(
        accepted.chat_id,
        accepted.run_id,
        AnswerData(
            blocks=(
                AnswerBlockData(
                    markdown="回答",
                    references=(
                        DisplayReferenceData(
                            reference_id=reference_id,
                            source_type="pdf",
                            label="資料",
                            relative_path="manual.pdf",
                            page_start=1,
                            page_end=2,
                        ),
                    ),
                ),
            ),
            artifacts=(
                ArtifactData(
                    artifact_id=artifact_id,
                    mime_type="text/html",
                    relative_path="report.html",
                ),
            ),
        ),
    )

    assert repository.get_reference(reference_id).relative_path == "manual.pdf"
    assert repository.get_artifact(artifact_id).relative_path == "report.html"
    assert repository.latest_artifact_id_for_test() == artifact_id


def test_memory_repository_rejects_cancel_for_terminal_run() -> None:
    """観点：メモリRepository IF。確認：終端済みrunのキャンセルを競合にする。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    repository.set_run_state(accepted.chat_id, accepted.run_id, "完了")

    try:
        repository.cancel_run(accepted.chat_id, accepted.run_id)
    except AppError as exc:
        assert exc.error_class is ErrorClass.CONFLICT
    else:
        raise AssertionError("終端済みrunのキャンセル競合が発生しませんでした。")


def test_memory_repository_rejects_missing_reference_artifact_and_latest() -> None:
    """観点：メモリRepository IF。

    確認：未保存の参照元、成果物、直近成果物IDをNOT_FOUNDにする。
    """
    repository = InMemoryChatRepository()

    try:
        repository.get_reference(uuid4())
    except AppError as exc:
        assert exc.error_class is ErrorClass.NOT_FOUND
    else:
        raise AssertionError("対象なし参照元の例外が発生しませんでした。")

    try:
        repository.get_artifact(uuid4())
    except AppError as exc:
        assert exc.error_class is ErrorClass.NOT_FOUND
    else:
        raise AssertionError("対象なし成果物の例外が発生しませんでした。")

    try:
        repository.latest_artifact_id_for_test()
    except AppError as exc:
        assert exc.error_class is ErrorClass.NOT_FOUND
    else:
        raise AssertionError("直近成果物なしの例外が発生しませんでした。")


def test_memory_repository_rejects_missing_chat_and_run() -> None:
    """観点：メモリRepository IF。確認：対象なしチャットとrunをNOT_FOUNDにする。"""
    repository = InMemoryChatRepository()
    missing_chat_id = uuid4()

    try:
        repository.get_chat_detail(missing_chat_id)
    except AppError as exc:
        assert exc.error_class is ErrorClass.NOT_FOUND
    else:
        raise AssertionError("対象なしチャットの例外が発生しませんでした。")

    accepted = repository.create_chat_with_first_run("資料を要約")
    try:
        repository.get_run_state(accepted.chat_id, uuid4())
    except AppError as exc:
        assert exc.error_class is ErrorClass.NOT_FOUND
    else:
        raise AssertionError("対象なしrunの例外が発生しませんでした。")


def test_memory_repository_lists_unfinished_runs_for_recovery() -> None:
    """観点：起動時回復Repository IF。確認：未完了runだけを回復対象として返す。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("受付")
    running = repository.create_chat_with_first_run("実行中")
    terminal = repository.create_chat_with_first_run("完了")
    repository.set_run_state(running.chat_id, running.run_id, "実行中")
    repository.set_run_state(terminal.chat_id, terminal.run_id, "完了")

    unfinished = repository.list_unfinished_runs_for_recovery()

    assert [(run.chat_id, run.run_id, run.state) for run in unfinished] == [
        (accepted.chat_id, accepted.run_id, "受付"),
        (running.chat_id, running.run_id, "実行中"),
    ]


def test_memory_repository_saves_and_loads_codex_runtime_context() -> None:
    """観点：チャットRepository IF。

    確認：作業領域IDとCodex側resume IDを保存取得できる。
    """
    repository = InMemoryChatRepository()
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


def test_memory_repository_updates_state_conditionally_and_saves_deadline() -> None:
    """観点：状態条件付き更新。

    確認：期待状態に一致する場合だけ状態とexecution_deadline_atを更新する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    deadline = datetime(2026, 5, 9, 10, 5, tzinfo=UTC)

    updated = repository.update_run_state_if_current(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        expected_states=("受付",),
        state="実行中",
        execution_deadline_at=deadline,
    )
    stale = repository.update_run_state_if_current(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        expected_states=("受付",),
        state="エラー",
    )

    assert updated is True
    assert stale is False
    detail = repository.get_chat_detail(accepted.chat_id)
    assert detail.runs[0].state == "実行中"
    assert (
        repository.run_execution_deadline_for_test(accepted.chat_id, accepted.run_id)
        == deadline
    )

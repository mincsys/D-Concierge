from dataclasses import dataclass, field
from uuid import UUID

import pytest

from backend.application.chat.delete_chat import DeleteChatUseCase
from backend.application.chat.execute_chat_deletion import (
    ExecuteChatDeletionUseCase,
)
from backend.application.ports.codex.cancel_request_result import CancelRequestResult
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    ArtifactData,
)
from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.dto import DispatchResult
from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.shared.errors.errors import ChatDeletingError, ChatNotFoundError
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_delete_chat_use_case_marks_chat_deleting_and_dispatches_job() -> None:
    """観点：チャット削除受付処理。

    確認：対象チャットを削除中へ更新し、物理削除ジョブを登録する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("削除対象")
    dispatcher = RecordingDeletionDispatcher()
    usecase = DeleteChatUseCase(repository=repository, deletion_dispatcher=dispatcher)

    result = usecase.execute(accepted.chat_id, trace_id="trace-delete-1")

    assert result.chat_id == accepted.chat_id
    assert result.chat_state is ChatState.DELETING
    assert repository.chat_state_for_test(accepted.chat_id) is ChatState.DELETING
    assert dispatcher.registered == [(accepted.chat_id, "trace-delete-1")]


def test_delete_chat_use_case_is_idempotent_for_deleting_chat() -> None:
    """観点：チャット削除受付処理の冪等性。

    確認：削除中チャットへの再送も削除受付済みとして応答する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("削除対象")
    repository.mark_chat_deleting(accepted.chat_id)
    dispatcher = RecordingDeletionDispatcher()
    usecase = DeleteChatUseCase(repository=repository, deletion_dispatcher=dispatcher)

    result = usecase.execute(accepted.chat_id, trace_id="trace-delete-2")

    assert result.chat_state is ChatState.DELETING
    assert dispatcher.registered == [(accepted.chat_id, "trace-delete-2")]


def test_delete_chat_use_case_returns_accepted_when_dispatch_fails() -> None:
    """観点：削除Dispatcher登録失敗。

    確認：チャット状態更新が成立していれば受付応答を返し、チャットを削除中のまま維持する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("削除対象")
    usecase = DeleteChatUseCase(
        repository=repository,
        deletion_dispatcher=FailingDeletionDispatcher(),
    )

    result = usecase.execute(accepted.chat_id, trace_id="trace-delete-3")

    assert result.chat_state is ChatState.DELETING
    assert repository.chat_state_for_test(accepted.chat_id) is ChatState.DELETING


def test_execute_chat_deletion_waits_after_requesting_cancel_for_unfinished_run() -> (
    None
):
    """観点：チャット物理削除処理。

    確認：未完了runがある場合はキャンセル要求を行い、作業領域・成果物・DB削除へ進まない。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("実行中削除")
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.RUNNING)
    repository.mark_chat_deleting(accepted.chat_id)
    cancel_requester = RecordingCancelRequester()
    workdir_cleanup = RecordingSessionWorkdirCleanup()
    artifact_deletion = RecordingArtifactDeletion()
    usecase = ExecuteChatDeletionUseCase(
        repository=repository,
        cancel_requester=cancel_requester,
        session_workdir_cleanup=workdir_cleanup,
        artifact_deletion=artifact_deletion,
    )

    usecase.execute(accepted.chat_id, trace_id="trace-physical-1")

    assert cancel_requester.requests == [accepted.run_id]
    assert workdir_cleanup.deleted == []
    assert artifact_deletion.deleted == []
    assert (
        repository.get_chat_deletion_target(accepted.chat_id).chat_id
        == accepted.chat_id
    )


def test_execute_chat_deletion_removes_files_then_database_for_terminal_chat() -> None:
    """観点：チャット物理削除処理。

    確認：未完了runがない場合は作業領域、保存済み成果物、DBデータの順で削除する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("完了済み削除")
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.COMPLETED)
    repository.save_completed_answer(
        accepted.chat_id,
        accepted.run_id,
        AnswerData(
            blocks=(
                AnswerBlockData(
                    markdown="回答",
                    artifacts=(
                        ArtifactData(
                            artifact_id=UUID("00000000-0000-0000-0000-000000000777"),
                            mime_type="image/svg+xml",
                            relative_path="run-id/chart.svg",
                        ),
                    ),
                ),
            ),
        ),
    )
    repository.mark_chat_deleting(accepted.chat_id)
    target = repository.get_chat_deletion_target(accepted.chat_id)
    workdir_cleanup = RecordingSessionWorkdirCleanup()
    artifact_deletion = RecordingArtifactDeletion()
    usecase = ExecuteChatDeletionUseCase(
        repository=repository,
        cancel_requester=RecordingCancelRequester(),
        session_workdir_cleanup=workdir_cleanup,
        artifact_deletion=artifact_deletion,
    )

    usecase.execute(accepted.chat_id, trace_id="trace-physical-2")

    assert workdir_cleanup.deleted == [(target.user_id, target.session_id)]
    assert artifact_deletion.deleted == [("run-id/chart.svg",)]
    with pytest.raises(ChatNotFoundError):
        repository.get_chat_detail(accepted.chat_id)


def test_execute_chat_deletion_keeps_chat_deleting_when_file_delete_fails() -> None:
    """観点：チャット物理削除失敗。

    確認：作業領域削除に失敗した場合はDB削除へ進まず、対象チャットを削除中のまま維持する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("削除失敗")
    repository.set_run_state(accepted.chat_id, accepted.run_id, RunState.COMPLETED)
    repository.mark_chat_deleting(accepted.chat_id)
    usecase = ExecuteChatDeletionUseCase(
        repository=repository,
        cancel_requester=RecordingCancelRequester(),
        session_workdir_cleanup=FailingSessionWorkdirCleanup(),
        artifact_deletion=RecordingArtifactDeletion(),
    )

    usecase.execute(accepted.chat_id, trace_id="trace-physical-failed")

    assert repository.chat_state_for_test(accepted.chat_id) is ChatState.DELETING
    with pytest.raises(ChatDeletingError):
        repository.get_chat_detail(accepted.chat_id)


@dataclass(slots=True)
class RecordingDeletionDispatcher:
    registered: list[tuple[UUID, str]] = field(default_factory=list)

    def register(self, chat_id: UUID, trace_id: str) -> DispatchResult:
        self.registered.append((chat_id, trace_id))
        return DispatchResult(status=DispatchStatus.REGISTERED)


class FailingDeletionDispatcher:
    def register(self, chat_id: UUID, trace_id: str) -> DispatchResult:
        _ = chat_id, trace_id
        return DispatchResult(
            status=DispatchStatus.FAILED,
            failure_reason="executor closed",
        )


@dataclass(slots=True)
class RecordingCancelRequester:
    requests: list[UUID] = field(default_factory=list)

    def request_cancel(self, run_id: UUID) -> CancelRequestResult:
        self.requests.append(run_id)
        return CancelRequestResult.SENT


@dataclass(slots=True)
class RecordingSessionWorkdirCleanup:
    deleted: list[tuple[str, UUID]] = field(default_factory=list)

    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None:
        self.deleted.append((user_id, session_id))


class FailingSessionWorkdirCleanup:
    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None:
        _ = user_id, session_id
        raise OSError("cleanup failed")


@dataclass(slots=True)
class RecordingArtifactDeletion:
    deleted: list[tuple[str, ...]] = field(default_factory=list)

    def delete_saved_artifacts(self, storage_paths: tuple[str, ...]) -> None:
        self.deleted.append(storage_paths)

from dataclasses import dataclass, field
from uuid import UUID

from backend.application.execution.recover_unfinished_runs import (
    RecoverUnfinishedRunsUseCase,
    RecoverySummary,
)
from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.application.ports.runtime.dto import DispatchResult
from backend.domain.execution.run_state import RunState
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_recover_unfinished_runs_reregisters_and_terminalizes_leftover_runs() -> None:
    """観点：起動時回復。確認：未完了runを状態別の回復先へ整合する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("accepted run")
    running = repository.create_chat_with_first_run("running run")
    validating = repository.create_chat_with_first_run("validating run")
    canceling = repository.create_chat_with_first_run("cancel requested run")
    completed = repository.create_chat_with_first_run("completed run")
    repository.set_run_state(running.chat_id, running.run_id, RunState.RUNNING)
    repository.set_run_state(validating.chat_id, validating.run_id, RunState.VALIDATING)
    repository.set_run_state(
        canceling.chat_id,
        canceling.run_id,
        RunState.CANCEL_REQUESTED,
    )
    repository.set_run_state(completed.chat_id, completed.run_id, RunState.COMPLETED)
    dispatcher = RecordingDispatcher()
    usecase = RecoverUnfinishedRunsUseCase(
        repository=repository,
        run_dispatcher=dispatcher,
    )

    summary = usecase.execute(trace_id="trace-301")

    assert summary == RecoverySummary(
        reregistered=1,
        marked_error=2,
        canceled=1,
        failed=0,
    )
    assert dispatcher.registered == [(accepted.chat_id, accepted.run_id)]
    assert repository.get_chat_detail(accepted.chat_id).runs[0].state is (
        RunState.ACCEPTED
    )
    assert repository.get_chat_detail(running.chat_id).runs[0].state is RunState.ERROR
    assert repository.get_chat_detail(validating.chat_id).runs[0].state is (
        RunState.ERROR
    )
    assert repository.get_chat_detail(canceling.chat_id).runs[0].state is (
        RunState.CANCELED
    )
    assert repository.get_chat_detail(completed.chat_id).runs[0].state is (
        RunState.COMPLETED
    )


def test_recover_unfinished_runs_marks_accepted_run_error_when_dispatch_fails() -> None:
    """観点：起動時回復。確認：受付run再登録失敗時は対象runをエラーへ更新して継続する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("accepted run")
    running = repository.create_chat_with_first_run("running run")
    repository.set_run_state(running.chat_id, running.run_id, RunState.RUNNING)
    dispatcher = FailingDispatcher()
    usecase = RecoverUnfinishedRunsUseCase(
        repository=repository,
        run_dispatcher=dispatcher,
    )

    summary = usecase.execute(trace_id="trace-302")

    assert summary == RecoverySummary(
        reregistered=0,
        marked_error=2,
        canceled=0,
        failed=1,
    )
    assert dispatcher.registered == [(accepted.chat_id, accepted.run_id)]
    accepted_run = repository.get_chat_detail(accepted.chat_id).runs[0]
    running_run = repository.get_chat_detail(running.chat_id).runs[0]
    assert accepted_run.state is RunState.ERROR
    assert accepted_run.user_message == "アプリ起動時に処理を再開できませんでした。"
    assert running_run.state is RunState.ERROR


@dataclass(slots=True)
class RecordingDispatcher:
    registered: list[tuple[UUID, UUID]] = field(default_factory=list)

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str = "",
    ) -> DispatchResult:
        _ = trace_id
        self.registered.append((chat_id, run_id))
        return DispatchResult(status=DispatchStatus.REGISTERED)


@dataclass(slots=True)
class FailingDispatcher:
    registered: list[tuple[UUID, UUID]] = field(default_factory=list)

    def register(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str = "",
    ) -> DispatchResult:
        _ = trace_id
        self.registered.append((chat_id, run_id))
        return DispatchResult(
            status=DispatchStatus.FAILED,
            failure_reason="executor closed",
        )

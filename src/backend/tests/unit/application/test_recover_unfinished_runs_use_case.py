from dataclasses import dataclass, field
from uuid import UUID

from backend.application.execution.dispatcher import DispatchResult
from backend.application.execution.recover_unfinished_runs import (
    RecoverUnfinishedRunsUseCase,
    RecoverySummary,
)
from backend.infrastructure.memory.repository import InMemoryChatRepository


def test_recover_unfinished_runs_reregisters_and_terminalizes_leftover_runs() -> None:
    """観点：起動時回復。確認：未完了runを状態別の回復先へ整合する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("受付")
    running = repository.create_chat_with_first_run("実行中")
    validating = repository.create_chat_with_first_run("検証中")
    canceling = repository.create_chat_with_first_run("キャンセル要求中")
    completed = repository.create_chat_with_first_run("完了")
    repository.set_run_state(running.chat_id, running.run_id, "実行中")
    repository.set_run_state(validating.chat_id, validating.run_id, "検証中")
    repository.set_run_state(canceling.chat_id, canceling.run_id, "キャンセル要求中")
    repository.set_run_state(completed.chat_id, completed.run_id, "完了")
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
    assert repository.get_chat_detail(accepted.chat_id).runs[0].state == "受付"
    assert repository.get_chat_detail(running.chat_id).runs[0].state == "エラー"
    assert repository.get_chat_detail(validating.chat_id).runs[0].state == "エラー"
    assert repository.get_chat_detail(canceling.chat_id).runs[0].state == (
        "キャンセル済み"
    )
    assert repository.get_chat_detail(completed.chat_id).runs[0].state == "完了"


def test_recover_unfinished_runs_marks_accepted_run_error_when_dispatch_fails() -> None:
    """観点：起動時回復。確認：受付run再登録失敗時は対象runをエラーへ更新して継続する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("受付")
    running = repository.create_chat_with_first_run("実行中")
    repository.set_run_state(running.chat_id, running.run_id, "実行中")
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
    assert accepted_run.state == "エラー"
    assert accepted_run.user_message == "アプリ起動時に処理を再開できませんでした。"
    assert running_run.state == "エラー"


@dataclass(slots=True)
class RecordingDispatcher:
    registered: list[tuple[UUID, UUID]] = field(default_factory=list)

    def register(self, chat_id: UUID, run_id: UUID) -> DispatchResult:
        self.registered.append((chat_id, run_id))
        return DispatchResult(status="registered")


@dataclass(slots=True)
class FailingDispatcher:
    registered: list[tuple[UUID, UUID]] = field(default_factory=list)

    def register(self, chat_id: UUID, run_id: UUID) -> DispatchResult:
        self.registered.append((chat_id, run_id))
        return DispatchResult(status="failed", failure_reason="executor closed")

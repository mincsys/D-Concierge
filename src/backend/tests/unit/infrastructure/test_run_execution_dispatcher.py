from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from uuid import UUID

from backend.infrastructure.runtime.run_execution_dispatcher import (
    InProcessRunExecutionDispatcher,
)


def test_dispatcher_registers_run_to_background_executor() -> None:
    """観点：RunExecutionDispatcher IF。

    確認：受付済みrunをバックグラウンドタスクへ登録し、実行時にUseCaseへ渡す。
    """
    run_executor = RecordingRunExecutor()
    background_executor = HoldingBackgroundExecutor()
    dispatcher = InProcessRunExecutionDispatcher(
        run_executor=run_executor,
        background_executor=background_executor,
    )
    chat_id = UUID("00000000-0000-0000-0000-000000000401")
    run_id = UUID("00000000-0000-0000-0000-000000000402")

    result = dispatcher.register(chat_id, run_id, "trace-401")
    background_executor.run_next()

    assert result.status == "registered"
    assert run_executor.executed == [(chat_id, run_id, "trace-401")]


def test_dispatcher_rejects_duplicate_run_while_active() -> None:
    """観点：RunExecutionDispatcher IF。

    確認：同一runを同時に複数の実行タスクへ登録しない。
    """
    dispatcher = InProcessRunExecutionDispatcher(
        run_executor=RecordingRunExecutor(),
        background_executor=HoldingBackgroundExecutor(),
    )
    chat_id = UUID("00000000-0000-0000-0000-000000000403")
    run_id = UUID("00000000-0000-0000-0000-000000000404")

    first = dispatcher.register(chat_id, run_id, "trace-403")
    second = dispatcher.register(chat_id, run_id, "trace-403")

    assert first.status == "registered"
    assert second.status == "already_registered"


def test_dispatcher_allows_reregister_after_task_finishes() -> None:
    """観点：RunExecutionDispatcher IF。

    確認：登録済みrunのタスク終了後は、同一runの再登録を妨げない。
    """
    background_executor = HoldingBackgroundExecutor()
    dispatcher = InProcessRunExecutionDispatcher(
        run_executor=RecordingRunExecutor(),
        background_executor=background_executor,
    )
    chat_id = UUID("00000000-0000-0000-0000-000000000405")
    run_id = UUID("00000000-0000-0000-0000-000000000406")

    dispatcher.register(chat_id, run_id, "trace-405")
    background_executor.run_next()
    result = dispatcher.register(chat_id, run_id, "trace-405")

    assert result.status == "registered"


def test_dispatcher_returns_failed_when_background_registration_fails() -> None:
    """観点：RunExecutionDispatcher IF異常系。

    確認：バックグラウンド登録失敗を失敗結果として返し、runの登録状態を残さない。
    """
    dispatcher = InProcessRunExecutionDispatcher(
        run_executor=RecordingRunExecutor(),
        background_executor=FailingBackgroundExecutor(),
    )
    chat_id = UUID("00000000-0000-0000-0000-000000000407")
    run_id = UUID("00000000-0000-0000-0000-000000000408")

    failed = dispatcher.register(chat_id, run_id, "trace-407")
    retried = dispatcher.register(chat_id, run_id, "trace-407")

    assert failed.status == "failed"
    assert failed.failure_reason == "登録できません。"
    assert retried.status == "failed"


@dataclass(slots=True)
class RecordingRunExecutor:
    """テスト用チャット実行UseCase。"""

    executed: list[tuple[UUID, UUID, str]] = field(default_factory=list)

    def execute(self, chat_id: UUID, run_id: UUID, trace_id: str = "") -> None:
        """実行対象を記録する。"""
        self.executed.append((chat_id, run_id, trace_id))


@dataclass(slots=True)
class HoldingBackgroundExecutor:
    """登録タスクを任意のタイミングで実行するテスト用Executor。"""

    tasks: list[Callable[[], None]] = field(default_factory=list)

    def submit(self, task: Callable[[], None]) -> Future[None]:
        """タスクを保持する。"""
        self.tasks.append(task)
        future: Future[None] = Future()
        return future

    def run_next(self) -> None:
        """次の登録タスクを実行する。"""
        task = self.tasks.pop(0)
        task()


class FailingBackgroundExecutor:
    """登録失敗を返すテスト用Executor。"""

    def submit(self, task: Callable[[], None]) -> Future[None]:
        """登録失敗を発生させる。"""
        raise RuntimeError("登録できません。")

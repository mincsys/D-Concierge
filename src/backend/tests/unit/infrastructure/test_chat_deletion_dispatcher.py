from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from uuid import UUID

from backend.application.ports.runtime.dispatch_status import DispatchStatus
from backend.infrastructure.runtime.chat_deletion_dispatcher import (
    InProcessChatDeletionDispatcher,
)


def test_chat_deletion_dispatcher_registers_chat_to_background_executor() -> None:
    """観点：ChatDeletionDispatcher IF。

    確認：削除対象チャットをバックグラウンドタスクへ登録し、実行UseCaseへ渡す。
    """
    deletion_executor = RecordingDeletionExecutor()
    background_executor = HoldingBackgroundExecutor()
    dispatcher = InProcessChatDeletionDispatcher(
        deletion_executor=deletion_executor,
        background_executor=background_executor,
    )
    chat_id = UUID("00000000-0000-0000-0000-000000000801")

    result = dispatcher.register(chat_id, "trace-801")
    background_executor.run_next()

    assert result.status is DispatchStatus.REGISTERED
    assert deletion_executor.executed == [(chat_id, "trace-801")]


def test_chat_deletion_dispatcher_rejects_duplicate_chat_while_active() -> None:
    """観点：ChatDeletionDispatcher IF。

    確認：同一チャットの削除ジョブを同時に複数登録しない。
    """
    dispatcher = InProcessChatDeletionDispatcher(
        deletion_executor=RecordingDeletionExecutor(),
        background_executor=HoldingBackgroundExecutor(),
    )
    chat_id = UUID("00000000-0000-0000-0000-000000000802")

    first = dispatcher.register(chat_id, "trace-802")
    second = dispatcher.register(chat_id, "trace-802")

    assert first.status is DispatchStatus.REGISTERED
    assert second.status is DispatchStatus.ALREADY_REGISTERED


def test_chat_deletion_dispatcher_allows_reregister_after_task_finishes() -> None:
    """観点：ChatDeletionDispatcher IF。

    確認：削除ジョブ終了後は同一チャットを再登録できる。
    """
    background_executor = HoldingBackgroundExecutor()
    dispatcher = InProcessChatDeletionDispatcher(
        deletion_executor=RecordingDeletionExecutor(),
        background_executor=background_executor,
    )
    chat_id = UUID("00000000-0000-0000-0000-000000000803")

    dispatcher.register(chat_id, "trace-803")
    background_executor.run_next()
    result = dispatcher.register(chat_id, "trace-803")

    assert result.status is DispatchStatus.REGISTERED


@dataclass(slots=True)
class RecordingDeletionExecutor:
    executed: list[tuple[UUID, str]] = field(default_factory=list)

    def execute(self, chat_id: UUID, trace_id: str = "") -> None:
        self.executed.append((chat_id, trace_id))


@dataclass(slots=True)
class HoldingBackgroundExecutor:
    tasks: list[Callable[[], None]] = field(default_factory=list)

    def submit(self, task: Callable[[], None]) -> Future[None]:
        self.tasks.append(task)
        future: Future[None] = Future()
        return future

    def run_next(self) -> None:
        task = self.tasks.pop(0)
        task()

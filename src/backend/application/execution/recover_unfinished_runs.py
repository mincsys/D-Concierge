from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.application.execution.dispatcher import DispatchResult
from backend.domain.execution.run_state_policy import RunState
from backend.infrastructure.memory.repository import UnfinishedRun
from backend.shared.errors import AppError

RECOVERY_ERROR_MESSAGE = "アプリ起動時に処理を再開できませんでした。"
RECOVERY_CANCEL_MESSAGE = "処理をキャンセルしました。"


@dataclass(frozen=True, slots=True)
class RecoverySummary:
    """起動時回復の処理件数。"""

    reregistered: int
    marked_error: int
    canceled: int
    failed: int


@dataclass(slots=True)
class _RecoveryCounter:
    reregistered: int = 0
    marked_error: int = 0
    canceled: int = 0
    failed: int = 0

    def to_summary(self) -> RecoverySummary:
        """公開用の回復処理サマリへ変換する。"""
        return RecoverySummary(
            reregistered=self.reregistered,
            marked_error=self.marked_error,
            canceled=self.canceled,
            failed=self.failed,
        )


class RecoveryRepository(Protocol):
    """起動時回復に必要なRepository境界。"""

    def list_unfinished_runs_for_recovery(self) -> tuple[UnfinishedRun, ...]:
        """未完了runを返す。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """runの状態と利用者向けメッセージを更新する。"""


class RunExecutionDispatcher(Protocol):
    """受付済みrunをバックグラウンド登録する境界。"""

    def register(self, chat_id: UUID, run_id: UUID) -> DispatchResult:
        """対象runの実行を登録する。"""


class RecoverUnfinishedRunsUseCase:
    """アプリ起動時に未完了runを再登録または終端状態へ整合する。"""

    def __init__(
        self,
        repository: RecoveryRepository,
        run_dispatcher: RunExecutionDispatcher,
    ) -> None:
        self._repository = repository
        self._run_dispatcher = run_dispatcher

    def execute(self, trace_id: str) -> RecoverySummary:
        """起動時回復対象の未完了runを状態別に処理する。"""
        _ = trace_id
        counter = _RecoveryCounter()
        for run in self._repository.list_unfinished_runs_for_recovery():
            self._recover_one(run, counter)
        return counter.to_summary()

    def _recover_one(self, run: UnfinishedRun, counter: _RecoveryCounter) -> None:
        try:
            match run.state:
                case "受付":
                    self._recover_accepted(run, counter)
                case "実行中" | "検証中":
                    self._mark_error(run)
                    counter.marked_error += 1
                case "キャンセル要求中":
                    self._repository.set_run_state(
                        run.chat_id,
                        run.run_id,
                        "キャンセル済み",
                        RECOVERY_CANCEL_MESSAGE,
                    )
                    counter.canceled += 1
                case _:
                    return
        except AppError:
            counter.failed += 1

    def _recover_accepted(
        self,
        run: UnfinishedRun,
        counter: _RecoveryCounter,
    ) -> None:
        result = self._run_dispatcher.register(run.chat_id, run.run_id)
        if result.status in {"registered", "already_registered"}:
            counter.reregistered += 1
            return

        self._mark_error(run)
        counter.marked_error += 1
        counter.failed += 1

    def _mark_error(self, run: UnfinishedRun) -> None:
        self._repository.set_run_state(
            run.chat_id,
            run.run_id,
            "エラー",
            RECOVERY_ERROR_MESSAGE,
        )

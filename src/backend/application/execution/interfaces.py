from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.application.execution.dto import CodexCancelResult
from backend.application.ports.database.dto import (
    IntermediateMessageData,
    SseRunSnapshot,
)


class CancelRunTargetLike(Protocol):
    """キャンセル対象runの読取結果構造。"""

    @property
    def user_id(self) -> str: ...

    @property
    def chat_id(self) -> UUID: ...

    @property
    def run_id(self) -> UUID: ...

    @property
    def state(self) -> str: ...

    @property
    def chat_state(self) -> str: ...


class RecoveryRunLike(Protocol):
    """起動時回復対象runの読取結果構造。"""

    @property
    def chat_id(self) -> UUID: ...

    @property
    def run_id(self) -> UUID: ...

    @property
    def state(self) -> str: ...


class CancelChatRunRepositoryLike(Protocol):
    """キャンセル受付ユースケースが必要とするRepository境界。"""

    def get_cancel_target(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
    ) -> CancelRunTargetLike | None: ...

    def update_run_state_if_current(
        self,
        run_id: UUID,
        expected_state: str,
        next_state: str,
        user_message: str | None = None,
    ) -> bool: ...


class RunEventPublisherLike(Protocol):
    """runイベント発行境界。"""

    def publish(
        self,
        run_id: UUID,
        event_name: str,
        payload_state: str,
        user_message: str | None = None,
    ) -> None: ...


class CodexRunCancellationLike(Protocol):
    """実行中Codex処理のキャンセル境界。"""

    def cancel(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
    ) -> CodexCancelResult: ...


class RecoverUnfinishedRunsRepositoryLike(Protocol):
    """起動時実行回復ユースケースが必要とするRepository境界。"""

    def list_unfinished_runs_for_recovery(self) -> tuple[RecoveryRunLike, ...]: ...

    def update_run_state_if_current(
        self,
        run_id: UUID,
        expected_state: str,
        next_state: str,
        user_message: str | None = None,
    ) -> bool: ...


class BackgroundExecutorLike(Protocol):
    """受付済みrunのbackground登録境界。"""

    def submit(self, run_id: UUID) -> bool: ...


class SseRunRepositoryLike(Protocol):
    """SSE初期送信用のrun読取境界。"""

    def get_run_state_for_sse(
        self,
        user_id: str,
        chat_id: UUID,
        run_id: UUID,
    ) -> SseRunSnapshot | None: ...

    def list_intermediate_messages_for_sse(
        self,
        run_id: UUID,
    ) -> tuple[IntermediateMessageData, ...]: ...

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.application.execution.dto import CodexCancelResult


class CodexRunCancellationPort(Protocol):
    """run ID単位でCodex実行停止を依頼する境界。"""

    def cancel(self, run_id: UUID, trace_id: str) -> CodexCancelResult: ...


class RunCancelRequesterLike(Protocol):
    """物理削除ユースケースへ渡す未完了run終了要求境界。"""

    def cancel(self, run_id: UUID, trace_id: str) -> str: ...


@dataclass(frozen=True, slots=True)
class CodexRunCancelRequester:
    """CodexRunnerのキャンセル結果を物理削除用の文字列statusへ変換する。"""

    codex_runner: CodexRunCancellationPort

    def cancel(self, run_id: UUID, trace_id: str) -> str:
        return self.codex_runner.cancel(run_id, trace_id).status

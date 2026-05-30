from typing import Protocol
from uuid import UUID

from backend.application.ports.codex.cancel_request_result import CancelRequestResult


class CancelableCodexRunner(Protocol):
    """キャンセル可能なCodexRunner境界。"""

    def cancel(self, run_id: UUID, trace_id: str) -> CancelRequestResult:
        """対象runのCodex Docker実行へ終了要求を送る。"""


class CodexCancelRequester:
    """CancelChatRunUseCase向けにCodexRunnerのcancelを適合させる。"""

    def __init__(self, codex_runner: CancelableCodexRunner) -> None:
        self._codex_runner = codex_runner

    def request_cancel(self, run_id: UUID) -> CancelRequestResult:
        """対象runのCodex Docker実行へ終了要求を送る。"""
        return self._codex_runner.cancel(run_id=run_id, trace_id="")

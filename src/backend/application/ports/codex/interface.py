from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.ports.codex.cancel_request_result import CancelRequestResult
from backend.application.ports.codex.dto import (
    CodexRunResult,
    ReferenceValidationResult,
    ValidatorCodexRunResult,
)
from backend.domain.answer.answer_candidate import ParsedAnswerCandidate


class CodexGenerationRunnerPort(Protocol):
    """生成用Codex実行境界。"""

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """生成用Codexを実行し、構造化結果を返す。"""


class ReferenceFileValidatorPort(Protocol):
    """参照元PDFファイル固定検証境界。"""

    def validate_reference_files(
        self,
        candidate: ParsedAnswerCandidate,
    ) -> ReferenceValidationResult:
        """回答候補の参照元PDFファイルとページ範囲を固定検証する。"""


class ValidatorCodexRunnerPort(Protocol):
    """検証用Codex 1回実行境界。"""

    def run_validation(
        self,
        chat_id: UUID,
        run_id: UUID,
        prompt: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
        has_artifact_links: bool = False,
    ) -> ValidatorCodexRunResult:
        """検証用Codexを1回実行し、rawな最終出力を返す。"""


class CancelRequesterPort(Protocol):
    """実行中Codexプロセスへの終了要求境界。"""

    def request_cancel(self, run_id: UUID) -> CancelRequestResult:
        """対象runの実行プロセスへ終了要求を送る。"""


class SessionWorkdirResolverPort(Protocol):
    """チャット単位の生成用Codex作業領域解決境界。"""

    def resolve_generation_workdir(self, chat_id: UUID) -> Path:
        """生成用Codexのセッション作業領域を返す。"""

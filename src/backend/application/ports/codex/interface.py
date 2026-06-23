from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.application.execution.dto import CodexCancelResult
from backend.application.ports.codex.dto import (
    CodexGenerationRequest,
    CodexGenerationResult,
    ReferenceValidationResult,
    ValidatorCodexRequest,
    ValidatorCodexResult,
)


class CodexGenerationRunnerPort(Protocol):
    """生成用Codex実行境界。"""

    def run_generation(
        self,
        request: CodexGenerationRequest,
    ) -> CodexGenerationResult: ...


class ValidatorCodexRunnerPort(Protocol):
    """検証用Codex実行境界。"""

    def run_validation(
        self,
        request: ValidatorCodexRequest,
    ) -> ValidatorCodexResult: ...


class ReferenceFileValidatorPort(Protocol):
    """参照元PDF固定検証境界。"""

    def validate_pdf_reference(
        self,
        path: str,
        page_start: int,
        page_end: int,
    ) -> ReferenceValidationResult: ...


class CancelRequesterPort(Protocol):
    """Codex実行キャンセル境界。"""

    def cancel(self, run_id: UUID, trace_id: str) -> CodexCancelResult: ...


class SessionWorkdirCleanupPort(Protocol):
    """Codex作業領域削除境界。"""

    def delete_session_workdirs(self, user_id: str, session_id: UUID) -> None: ...

    def delete_user_workdirs(self, user_id: str) -> None: ...

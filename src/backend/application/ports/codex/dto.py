from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CodexGenerationRequest:
    """生成用Codex実行要求DTO。"""

    chat_id: UUID
    run_id: UUID
    user_id: str
    session_id: UUID
    user_instruction: str
    resume_conversation_id: str | None
    regeneration_instruction: str | None
    remaining_seconds: int


@dataclass(frozen=True, slots=True)
class CodexGenerationResult:
    """生成用Codex実行結果DTO。"""

    conversation_id: str
    progress_messages: tuple[str, ...]
    final_answer_json: str
    artifacts_dir: Path


@dataclass(frozen=True, slots=True)
class ValidatorCodexRequest:
    """検証用Codex実行要求DTO。"""

    chat_id: UUID
    run_id: UUID
    user_id: str
    session_id: UUID
    candidate_json: str
    resume_conversation_id: str | None
    artifacts_readonly_dir: Path | None
    remaining_seconds: int


@dataclass(frozen=True, slots=True)
class ValidatorCodexResult:
    """検証用Codex実行結果DTO。"""

    conversation_id: str
    progress_messages: tuple[str, ...]
    final_result_json: str


@dataclass(frozen=True, slots=True)
class ReferenceValidationResult:
    """参照元PDF固定検証結果DTO。"""

    path: str
    page_start: int
    page_end: int
    exists: bool
    readable: bool
    page_count: int

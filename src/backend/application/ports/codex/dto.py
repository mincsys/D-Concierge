from dataclasses import dataclass
from typing import Literal

CancelRequestResult = Literal["sent", "already_exited", "not_registered"]


@dataclass(frozen=True, slots=True)
class CodexRunResult:
    """Codex生成結果。"""

    conversation_id: str
    intermediate_messages: tuple[str, ...]
    final_answer_json: str


@dataclass(frozen=True, slots=True)
class ReferenceValidationResult:
    """検証用Codexによる参照元検証結果。"""

    valid: bool
    comment: str | None = None

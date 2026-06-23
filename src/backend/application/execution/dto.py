from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type CodexCancelStatus = Literal["sent", "already_exited", "not_registered"]


@dataclass(frozen=True, slots=True)
class CancelChatRunResult:
    """キャンセル受付結果。"""

    state: str
    user_message: str


@dataclass(frozen=True, slots=True)
class CodexCancelResult:
    """Codex実行キャンセル境界の結果。"""

    status: CodexCancelStatus


@dataclass(frozen=True, slots=True)
class RecoverUnfinishedRunsResult:
    """起動時実行回復の処理件数。"""

    accepted_registered: int
    error_terminalized: int
    canceled_terminalized: int

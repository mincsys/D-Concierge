from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.domain.chat.chat_state import ChatState
from backend.domain.execution.run_state import RunState
from backend.domain.references.source_type import SourceType

SHARED_LOCAL_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True, slots=True)
class AcceptedRun:
    """受付済みrunのAPI応答に必要な情報。"""

    chat_id: UUID
    run_id: UUID
    state: RunState


@dataclass(frozen=True, slots=True)
class DeleteChatResult:
    """チャット削除受付APIの応答に必要な情報。"""

    chat_id: UUID
    chat_state: ChatState


@dataclass(frozen=True, slots=True)
class UnfinishedRun:
    """起動時回復対象の未完了run情報。"""

    chat_id: UUID
    run_id: UUID
    state: RunState


@dataclass(frozen=True, slots=True)
class ChatDeletionRun:
    """チャット物理削除前に確認するrun情報。"""

    run_id: UUID
    state: RunState


@dataclass(frozen=True, slots=True)
class ChatDeletionTarget:
    """チャット物理削除に必要な対象情報。"""

    chat_id: UUID
    local_user_id: UUID
    session_id: UUID
    unfinished_runs: tuple[ChatDeletionRun, ...]
    artifact_storage_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChatRuntimeContext:
    """Codex実行時に必要なチャット単位の内部コンテキスト。"""

    chat_id: UUID
    local_user_id: UUID
    session_id: UUID
    generation_conversation_id: str | None
    validation_conversation_id: str | None


@dataclass(frozen=True, slots=True)
class HistoryItem:
    """履歴一覧の1件分。"""

    chat_id: UUID
    title: str
    latest_run_id: UUID | None
    latest_state: RunState
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IntermediateMessageData:
    """中間メッセージ表示データ。"""

    text: str


@dataclass(frozen=True, slots=True)
class DisplayReferenceData:
    """表示用参照元メタ情報。"""

    reference_id: UUID
    source_type: SourceType
    label: str
    relative_path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ArtifactData:
    """保存済みCodex成果物の配信メタ情報。"""

    artifact_id: UUID
    mime_type: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class AnswerData:
    """回答表示データ。"""

    blocks: tuple[AnswerBlockData, ...]


@dataclass(frozen=True, slots=True)
class AnswerBlockData:
    """回答本文とその根拠参照元の表示データ。"""

    markdown: str
    references: tuple[DisplayReferenceData, ...] = ()
    artifacts: tuple[ArtifactData, ...] = ()


@dataclass(frozen=True, slots=True)
class RunDetail:
    """履歴詳細内のrun表示データ。"""

    run_id: UUID
    state: RunState
    user_instruction: str
    intermediate_messages: tuple[IntermediateMessageData, ...]
    answer: AnswerData | None
    user_message: str | None


@dataclass(frozen=True, slots=True)
class ChatDetail:
    """チャット詳細表示データ。"""

    chat_id: UUID
    title: str
    runs: tuple[RunDetail, ...]

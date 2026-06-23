from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccountUserData:
    """アカウント情報の永続化境界DTO。"""

    user_id: str
    user_name: str
    password_hash: str
    user_state: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LoginSessionData:
    """ログインセッション照合結果DTO。"""

    session_row_id: int
    token_hash: str
    user_id: str
    user_name: str
    user_state: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccountDeletionTarget:
    """アカウント物理削除で扱う対象DTO。"""

    user_id: str
    active_chat_session_ids: tuple[UUID, ...]
    unfinished_run_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class AcceptedRun:
    """受付済みrunの起動対象DTO。"""

    run_id: UUID
    chat_id: UUID
    user_id: str
    session_id: UUID
    state: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class UnfinishedRun:
    """起動時回復対象の未完了run DTO。"""

    run_id: UUID
    chat_id: UUID
    user_id: str
    session_id: UUID
    state: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class CancelRunTarget:
    """キャンセル受付で検証するrun DTO。"""

    user_id: str
    chat_id: UUID
    run_id: UUID
    state: str
    chat_state: str


@dataclass(frozen=True, slots=True)
class SseRunSnapshot:
    """SSE購読開始時に返すrun状態DTO。"""

    chat_id: UUID
    run_id: UUID
    state: str
    chat_state: str
    answer: AnswerData | None
    user_message: str | None


@dataclass(frozen=True, slots=True)
class ChatRuntimeContext:
    """チャット実行時に必要な永続化済み文脈DTO。"""

    chat_id: UUID
    user_id: str
    session_id: UUID
    generation_conversation_id: str | None
    validation_conversation_id: str | None
    user_instruction: str = ""


@dataclass(frozen=True, slots=True)
class HistoryItem:
    """履歴一覧表示用DTO。"""

    chat_id: UUID
    title: str
    latest_run_id: UUID | None
    latest_state: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DisplayReferenceData:
    """画面表示用参照元DTO。"""

    reference_id: UUID
    position: int
    source_type: str
    label: str
    path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ArtifactData:
    """画面配信用成果物DTO。"""

    artifact_id: UUID
    mime_type: str
    storage_path: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AnswerData:
    """runに紐づく採用済み回答DTO。"""

    blocks: tuple[AnswerBlockData, ...]


@dataclass(frozen=True, slots=True)
class AnswerBlockData:
    """回答ブロックDTO。"""

    answer_block_id: UUID
    position: int
    markdown: str
    references: tuple[DisplayReferenceData, ...]
    artifacts: tuple[ArtifactData, ...]


@dataclass(frozen=True, slots=True)
class IntermediateMessageData:
    """履歴再表示用の中間メッセージDTO。"""

    text: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChatRunData:
    """履歴詳細のrun表示DTO。"""

    run_id: UUID
    state: str
    user_instruction: str
    started_at: datetime
    intermediate_messages: tuple[IntermediateMessageData, ...]
    answer: AnswerData | None
    user_message: str | None


@dataclass(frozen=True, slots=True)
class ChatDetail:
    """チャット詳細再表示用DTO。"""

    chat_id: UUID
    title: str
    runs: tuple[ChatRunData, ...]


@dataclass(frozen=True, slots=True)
class ChatDeletionTarget:
    """チャット物理削除で扱う対象DTO。"""

    chat_id: UUID
    user_id: str
    session_id: UUID
    storage_paths: tuple[str, ...]
    unfinished_run_ids: tuple[UUID, ...] = ()

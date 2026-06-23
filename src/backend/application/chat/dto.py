from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ChatAcceptedResult:
    """チャット受付応答。"""

    chat_id: UUID
    run_id: UUID
    sse_url: str
    state: str


@dataclass(frozen=True, slots=True)
class HistoryItemResult:
    """履歴一覧の1項目。"""

    chat_id: UUID
    title: str
    latest_run_id: UUID | None
    latest_state: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class HistoryListResult:
    """履歴一覧取得結果。"""

    items: tuple[HistoryItemResult, ...]


@dataclass(frozen=True, slots=True)
class PdfLocatorResult:
    """PDF参照位置。"""

    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class DisplayReferenceResult:
    """画面表示用参照元。"""

    source_type: str
    label: str
    url: str
    locator: PdfLocatorResult


@dataclass(frozen=True, slots=True)
class AnswerBlockResult:
    """回答ブロック表示情報。"""

    markdown: str
    references: tuple[DisplayReferenceResult, ...]


@dataclass(frozen=True, slots=True)
class AnswerResult:
    """runに紐づく回答表示情報。"""

    blocks: tuple[AnswerBlockResult, ...]


@dataclass(frozen=True, slots=True)
class IntermediateMessageResult:
    """中間メッセージ表示情報。"""

    text: str


@dataclass(frozen=True, slots=True)
class ChatRunResult:
    """履歴詳細のrun表示情報。"""

    run_id: UUID
    state: str
    user_instruction: str
    intermediate_messages: tuple[IntermediateMessageResult, ...]
    answer: AnswerResult | None
    user_message: str | None


@dataclass(frozen=True, slots=True)
class ChatDetailResult:
    """履歴詳細取得結果。"""

    chat_id: UUID
    title: str
    runs: tuple[ChatRunResult, ...]


@dataclass(frozen=True, slots=True)
class DeleteChatResult:
    """チャット削除受付結果。"""

    chat_id: UUID
    chat_state: str

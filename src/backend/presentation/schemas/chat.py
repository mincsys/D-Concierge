from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChatInstructionRequest:
    """チャット受付リクエスト。"""

    user_instruction: str


@dataclass(frozen=True, slots=True)
class ChatAcceptedResponse:
    """チャット受付レスポンス。"""

    chat_id: str
    run_id: str
    sse_url: str
    state: str


@dataclass(frozen=True, slots=True)
class ChatHistoryItemResponse:
    """履歴一覧の1項目レスポンス。"""

    chat_id: str
    title: str
    latest_state: str
    updated_at: str
    latest_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class IntermediateMessageResponse:
    """中間メッセージレスポンス。"""

    text: str


@dataclass(frozen=True, slots=True)
class PdfLocatorResponse:
    """PDF参照位置レスポンス。"""

    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class DisplayReferenceResponse:
    """表示用参照元レスポンス。"""

    source_type: str
    label: str
    url: str
    locator: PdfLocatorResponse


@dataclass(frozen=True, slots=True)
class AnswerBlockResponse:
    """回答ブロックレスポンス。"""

    markdown: str
    references: tuple[DisplayReferenceResponse, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerResponse:
    """回答レスポンス。"""

    blocks: tuple[AnswerBlockResponse, ...]


@dataclass(frozen=True, slots=True)
class ChatRunResponse:
    """履歴詳細のrunレスポンス。"""

    run_id: str
    state: str
    user_instruction: str
    intermediate_messages: tuple[IntermediateMessageResponse, ...] = ()
    answer: AnswerResponse | None = None
    user_message: str | None = None


@dataclass(frozen=True, slots=True)
class ChatDetailResponse:
    """履歴詳細レスポンス。"""

    chat_id: str
    title: str
    runs: tuple[ChatRunResponse, ...]


@dataclass(frozen=True, slots=True)
class CancelChatRunResponse:
    """キャンセル受付レスポンス。"""

    state: str
    user_message: str


@dataclass(frozen=True, slots=True)
class DeleteChatResponse:
    """チャット削除受付レスポンス。"""

    chat_id: str
    chat_state: str

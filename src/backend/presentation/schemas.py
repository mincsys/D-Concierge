from dataclasses import dataclass, field
from typing import Literal

from backend.domain.execution.run_state_policy import RunState


@dataclass(frozen=True, slots=True)
class AppConfigResponseSchema:
    """アプリ設定取得APIの応答。"""

    welcome_message: str | None = None
    input_suggestions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ChatStartRequestSchema:
    """新規チャット開始と継続指示受付APIの要求。"""

    user_instruction: str


@dataclass(frozen=True, slots=True)
class ChatStartResponseSchema:
    """新規チャット開始と継続指示受付APIの応答。"""

    chat_id: str
    run_id: str
    sse_url: str
    state: RunState


@dataclass(frozen=True, slots=True)
class CancelChatRunResponseSchema:
    """キャンセル受付APIの応答。"""

    run_id: str
    state: Literal["キャンセル要求中"]
    user_message: str


@dataclass(frozen=True, slots=True)
class ChatHistoryItemResponseSchema:
    """履歴一覧APIの1件分の応答。"""

    chat_id: str
    title: str
    latest_run_id: str | None = None
    latest_state: RunState = "受付"
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class PdfLocatorSchema:
    """PDF参照元の表示位置。"""

    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class DisplayReferenceSchema:
    """表示用参照元メタ情報。"""

    source_type: Literal["pdf"]
    label: str
    url: str
    locator: PdfLocatorSchema


@dataclass(frozen=True, slots=True)
class IntermediateMessageResponseSchema:
    """中間メッセージ表示情報。"""

    text: str


@dataclass(frozen=True, slots=True)
class AnswerResponseSchema:
    """回答表示情報。"""

    blocks: list["AnswerBlockResponseSchema"]


@dataclass(frozen=True, slots=True)
class AnswerBlockResponseSchema:
    """回答ブロック表示情報。"""

    markdown: str
    references: list[DisplayReferenceSchema] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ChatRunResponseSchema:
    """チャット詳細内のrun応答。"""

    run_id: str
    state: RunState
    user_instruction: str
    intermediate_messages: list[IntermediateMessageResponseSchema] = field(
        default_factory=list
    )
    answer: AnswerResponseSchema | None = None
    user_message: str | None = None


@dataclass(frozen=True, slots=True)
class ChatDetailResponseSchema:
    """チャット詳細APIの応答。"""

    chat_id: str
    title: str
    runs: list[ChatRunResponseSchema]


@dataclass(frozen=True, slots=True)
class ErrorResponseSchema:
    """APIエラー応答。"""

    error: str
    message: str

# mypy: disable-error-code="explicit-any"
from pydantic import BaseModel, Field


class AppConfigResponseSchema(BaseModel):
    """アプリ設定取得APIの応答。"""

    welcome_message: str | None = None
    sub_welcome_message: str | None = None
    input_suggestions: list[str] = Field(default_factory=list)


class AuthUserResponseSchema(BaseModel):
    """認証済みユーザ公開情報。"""

    user_id: str
    user_name: str


class CurrentUserResponseSchema(BaseModel):
    """現在ユーザ応答。"""

    user: AuthUserResponseSchema


class RegisterAccountRequestSchema(BaseModel):
    """アカウント登録APIの要求。"""

    user_id: str
    user_name: str
    password: str
    password_confirmation: str


class LoginRequestSchema(BaseModel):
    """ログインAPIの要求。"""

    user_id: str
    password: str


class ChangeUserNameRequestSchema(BaseModel):
    """ユーザ名変更APIの要求。"""

    user_name: str


class ChangePasswordRequestSchema(BaseModel):
    """パスワード変更APIの要求。"""

    current_password: str
    new_password: str
    new_password_confirmation: str


class DeleteAccountResponseSchema(BaseModel):
    """アカウント削除受付APIの応答。"""

    account_state: str


class ChatStartRequestSchema(BaseModel):
    """新規チャット開始と継続指示受付APIの要求。"""

    user_instruction: str


class ChatStartResponseSchema(BaseModel):
    """新規チャット開始と継続指示受付APIの応答。"""

    chat_id: str
    run_id: str
    sse_url: str
    state: str


class CancelChatRunResponseSchema(BaseModel):
    """キャンセル受付APIの応答。"""

    run_id: str
    state: str
    user_message: str


class DeleteChatResponseSchema(BaseModel):
    """チャット削除受付APIの応答。"""

    chat_id: str
    chat_state: str


class ChatHistoryItemResponseSchema(BaseModel):
    """履歴一覧APIの1件分の応答。"""

    chat_id: str
    title: str
    latest_run_id: str | None = None
    latest_state: str = ""
    updated_at: str = ""


class PdfLocatorSchema(BaseModel):
    """PDF参照元の表示位置。"""

    page_start: int
    page_end: int


class DisplayReferenceSchema(BaseModel):
    """表示用参照元メタ情報。"""

    source_type: str
    label: str
    url: str
    locator: PdfLocatorSchema


class IntermediateMessageResponseSchema(BaseModel):
    """中間メッセージ表示情報。"""

    text: str


class AnswerBlockResponseSchema(BaseModel):
    """回答ブロック表示情報。"""

    markdown: str
    references: list[DisplayReferenceSchema] = Field(default_factory=list)


class AnswerResponseSchema(BaseModel):
    """回答表示情報。"""

    blocks: list[AnswerBlockResponseSchema]


class ChatRunResponseSchema(BaseModel):
    """チャット詳細内のrun応答。"""

    run_id: str
    state: str
    user_instruction: str
    intermediate_messages: list[IntermediateMessageResponseSchema] = Field(
        default_factory=list
    )
    answer: AnswerResponseSchema | None = None
    user_message: str | None = None


class ChatDetailResponseSchema(BaseModel):
    """チャット詳細APIの応答。"""

    chat_id: str
    title: str
    runs: list[ChatRunResponseSchema]


class ErrorResponseSchema(BaseModel):
    """APIエラー応答。"""

    error: str
    message: str
    field_errors: dict[str, str] | None = None

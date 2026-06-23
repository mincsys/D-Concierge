from __future__ import annotations

from uuid import UUID

from backend.application.account.errors import FieldValidationError
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


def normalize_instruction(user_instruction: str) -> str:
    """利用者指示の外側空白を除去し、空なら項目別エラーにする。"""

    normalized = user_instruction.strip()
    if not normalized:
        raise FieldValidationError(
            {"user_instruction": "ユーザ指示を入力してください。"},
        )
    return normalized


def build_title(user_instruction: str) -> str:
    """初回指示から履歴タイトルを生成する。"""

    title = " ".join(user_instruction.split())
    return title[:50]


def build_sse_url(chat_id: UUID, run_id: UUID) -> str:
    """対象runのSSE購読URLを生成する。"""

    return f"/api/chats/{chat_id}/runs/{run_id}/sse"


def dispatcher_failure(diagnostic_message: str) -> AppError:
    """dispatcher登録失敗を受付APIのシステムエラーへ変換する。"""

    return AppError(
        error_type=ErrorType.SYSTEM,
        trace=True,
        diagnostic_message=diagnostic_message or "チャット実行登録に失敗しました。",
    )

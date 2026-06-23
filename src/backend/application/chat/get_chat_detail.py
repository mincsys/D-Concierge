from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.application.chat.dto import (
    AnswerBlockResult,
    AnswerResult,
    ChatDetailResult,
    ChatRunResult,
    DisplayReferenceResult,
    IntermediateMessageResult,
    PdfLocatorResult,
)
from backend.application.chat.interfaces import ChatDetailRepositoryLike
from backend.application.ports.database.dto import (
    AnswerData,
    ChatRunData,
    DisplayReferenceData,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.shared.tracing.trace_id import TraceId


@dataclass(frozen=True, slots=True)
class GetChatDetailCommand:
    """履歴詳細取得要求。"""

    authenticated_user_id: str
    chat_id: UUID
    trace_id: TraceId


class GetChatDetailUseCase:
    """履歴詳細取得を調停する。"""

    def __init__(self, *, repository: ChatDetailRepositoryLike) -> None:
        self._repository = repository

    def execute(self, command: GetChatDetailCommand) -> ChatDetailResult:
        """指定チャットの保存済みrunと表示情報を返す。"""

        detail = self._repository.get_chat_detail(
            command.authenticated_user_id,
            command.chat_id,
        )
        if detail is None:
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="対象チャットが見つかりません。",
            )

        return ChatDetailResult(
            chat_id=detail.chat_id,
            title=detail.title,
            runs=tuple(_run_result(run) for run in detail.runs),
        )


def _run_result(run: ChatRunData) -> ChatRunResult:
    return ChatRunResult(
        run_id=run.run_id,
        state=run.state,
        user_instruction=run.user_instruction,
        intermediate_messages=tuple(
            IntermediateMessageResult(text=message.text)
            for message in run.intermediate_messages
        ),
        answer=_answer_result(run.answer),
        user_message=run.user_message,
    )


def _answer_result(answer: AnswerData | None) -> AnswerResult | None:
    if answer is None:
        return None
    return AnswerResult(
        blocks=tuple(
            AnswerBlockResult(
                markdown=block.markdown,
                references=tuple(
                    _reference_result(reference) for reference in block.references
                ),
            )
            for block in answer.blocks
        ),
    )


def _reference_result(reference: DisplayReferenceData) -> DisplayReferenceResult:
    return DisplayReferenceResult(
        source_type=reference.source_type,
        label=reference.label,
        url=f"/api/references/{reference.reference_id}",
        locator=PdfLocatorResult(
            page_start=reference.page_start,
            page_end=reference.page_end,
        ),
    )

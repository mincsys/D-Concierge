from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from backend.domain.answer.answer_candidate import (
    AnswerParseError,
    ParsedAnswerCandidate,
    parse_generation_final_output,
)

VALIDATION_FAILURE_MESSAGE = (
    "回答の確認に失敗したため、回答を表示できませんでした。"
    "ユーザ指示を具体化して再度お試しください。"
)

type ValidationStatus = Literal["採用可能", "再生成指示", "失敗"]


@dataclass(frozen=True, slots=True)
class ReferenceValidationResult:
    """検証用Codexによる参照元検証結果。"""

    valid: bool
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class AnswerValidationResult:
    """回答検証UseCaseの判定結果。"""

    status: ValidationStatus
    candidate: ParsedAnswerCandidate | None = None
    regeneration_instruction: str = ""
    user_message: str = ""


class ReferenceValidator(Protocol):
    """参照元検証境界。"""

    def validate_references(
        self,
        candidate: ParsedAnswerCandidate,
        chat_id: UUID | None = None,
        run_id: UUID | None = None,
        trace_id: str = "",
        timeout_seconds: int | None = None,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> ReferenceValidationResult:
        """回答候補の参照元が回答内容を支えるか検証する。"""


class ValidateAnswerUseCase:
    """回答候補の固定検証、参照元検証、再生成判断を行う。"""

    def __init__(
        self,
        reference_validator: ReferenceValidator,
        max_retries: int,
    ) -> None:
        self._reference_validator = reference_validator
        self._max_retries = max_retries

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        chat_id: UUID | None = None,
        run_id: UUID | None = None,
        trace_id: str = "",
        timeout_seconds: int | None = None,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> AnswerValidationResult:
        """回答候補を検証し、採用可否または再生成判断を返す。"""
        try:
            candidate = parse_generation_final_output(raw_answer_json)
        except AnswerParseError as exc:
            return self._regeneration_or_failure(
                retry_count=retry_count,
                reason=exc.regeneration_instruction or "固定検証に失敗しました。",
            )

        validation = self._reference_validator.validate_references(
            candidate,
            chat_id,
            run_id,
            trace_id,
            timeout_seconds,
            on_intermediate_message,
        )
        if validation.valid:
            return AnswerValidationResult(status="採用可能", candidate=candidate)

        return self._regeneration_or_failure(
            retry_count=retry_count,
            reason=_regeneration_reason(validation),
        )

    def _regeneration_or_failure(
        self,
        retry_count: int,
        reason: str,
    ) -> AnswerValidationResult:
        if retry_count < self._max_retries:
            return AnswerValidationResult(
                status="再生成指示",
                regeneration_instruction=reason,
            )
        return AnswerValidationResult(
            status="失敗",
            user_message=VALIDATION_FAILURE_MESSAGE,
        )


def _regeneration_reason(validation: ReferenceValidationResult) -> str:
    if validation.comment is None or validation.comment.strip() == "":
        return "参照元検証に失敗しました。"
    return validation.comment

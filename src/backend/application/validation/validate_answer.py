from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from backend.application.artifacts.validate_artifact_links import (
    ArtifactLinkValidationResult,
    ArtifactLinkValidator,
)
from backend.application.ports.codex.dto import ReferenceValidationResult
from backend.application.ports.codex.interface import ReferenceValidatorPort
from backend.domain.answer.answer_candidate import (
    AnswerParseError,
    ParsedAnswerCandidate,
    parse_generation_final_output,
)

VALIDATION_FAILURE_MESSAGE = "回答生成に失敗しました。再度お試しください。"

type ValidationStatus = Literal["採用可能", "再生成指示", "失敗"]


@dataclass(frozen=True, slots=True)
class AnswerValidationResult:
    """回答検証UseCaseの判定結果。"""

    status: ValidationStatus
    candidate: ParsedAnswerCandidate | None = None
    regeneration_instruction: str = ""
    user_message: str = ""


class AnswerArtifactLinkValidator(Protocol):
    """回答本文内のCodex成果物リンク固定検証境界。"""

    def validate(
        self,
        markdowns: tuple[str, ...],
        session_workdir: Path | None,
    ) -> ArtifactLinkValidationResult:
        """回答本文内の成果物リンクを検証する。"""


class ValidateAnswerUseCase:
    """回答候補の固定検証、参照元検証、再生成判断を行う。"""

    def __init__(
        self,
        reference_validator: ReferenceValidatorPort,
        max_retries: int,
        artifact_link_validator: AnswerArtifactLinkValidator | None = None,
    ) -> None:
        self._reference_validator = reference_validator
        self._max_retries = max_retries
        self._artifact_link_validator = (
            artifact_link_validator
            if artifact_link_validator is not None
            else ArtifactLinkValidator()
        )

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID | None = None,
        run_id: UUID | None = None,
        trace_id: str = "",
        timeout_seconds: int | None = None,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        """回答候補を検証し、採用可否または再生成判断を返す。"""
        try:
            candidate = parse_generation_final_output(raw_answer_json)
        except AnswerParseError as exc:
            return self._regeneration_or_failure(
                retry_count=retry_count,
                reason=exc.regeneration_instruction or "固定検証に失敗しました。",
            )

        artifact_link_validation = self._artifact_link_validator.validate(
            markdowns=tuple(block.markdown for block in candidate.blocks),
            session_workdir=session_workdir,
        )
        if not artifact_link_validation.valid:
            return self._regeneration_or_failure(
                retry_count=retry_count,
                reason=artifact_link_validation.regeneration_instruction,
            )

        validation = self._reference_validator.validate_references(
            candidate=candidate,
            user_instruction=user_instruction,
            chat_id=chat_id,
            run_id=run_id,
            trace_id=trace_id,
            timeout_seconds=timeout_seconds,
            on_intermediate_message=on_intermediate_message,
            session_workdir=session_workdir,
            has_artifact_links=artifact_link_validation.has_artifact_links,
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

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.artifacts.validate_artifact_links import (
    ArtifactLinkValidationResult,
    ArtifactLinkValidator,
)
from backend.application.ports.codex.interface import ReferenceValidatorPort
from backend.application.validation.instruction_messages import (
    get_answer_parse_failure_message,
    get_artifact_link_validation_message,
    get_reference_validation_failed_message,
)
from backend.application.validation.validation_status import ValidationStatus
from backend.domain.answer.answer_candidate import (
    AnswerParseError,
    ParsedAnswerCandidate,
    parse_generation_final_output,
)
from backend.domain.validation.retry_policy import RetryPolicy
from backend.shared.user_messages import VALIDATION_FAILURE_MESSAGE


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
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._reference_validator = reference_validator
        self._retry_policy = (
            retry_policy if retry_policy is not None else RetryPolicy(max_retries)
        )
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
                reason=get_answer_parse_failure_message(exc.failure),
            )

        artifact_link_validation = self._artifact_link_validator.validate(
            markdowns=tuple(block.markdown for block in candidate.blocks),
            session_workdir=session_workdir,
        )
        if not artifact_link_validation.valid:
            return self._regeneration_or_failure(
                retry_count=retry_count,
                reason=get_artifact_link_validation_message(artifact_link_validation),
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
            return AnswerValidationResult(
                status=ValidationStatus.ACCEPTED,
                candidate=candidate,
            )

        return self._regeneration_or_failure(
            retry_count=retry_count,
            reason=get_reference_validation_failed_message(validation),
        )

    def _regeneration_or_failure(
        self,
        retry_count: int,
        reason: str,
    ) -> AnswerValidationResult:
        if self._retry_policy.can_retry(retry_count):
            return AnswerValidationResult(
                status=ValidationStatus.REGENERATE,
                regeneration_instruction=reason,
            )
        return AnswerValidationResult(
            status=ValidationStatus.FAILED,
            user_message=VALIDATION_FAILURE_MESSAGE,
        )

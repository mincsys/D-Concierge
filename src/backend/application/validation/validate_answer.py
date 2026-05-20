from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.artifacts.validate_artifact_links import (
    ArtifactLinkValidationResult,
    ArtifactLinkValidator,
)
from backend.application.ports.codex.dto import ReferenceValidationResult
from backend.application.ports.codex.interface import (
    ReferenceFileValidatorPort,
    ValidatorCodexRunnerPort,
)
from backend.application.validation.instruction_messages import (
    get_answer_parse_failure_message,
    get_artifact_link_validation_message,
    get_reference_validation_failed_message,
)
from backend.application.validation.validate_validator_output import (
    ParsedValidatorOutput,
    parse_validator_final_output,
)
from backend.application.validation.validation_status import ValidationStatus
from backend.application.validation.validator_prompts import (
    build_validator_prompt,
    build_validator_result_retry_prompt,
)
from backend.domain.answer.answer_candidate import (
    AnswerParseError,
    ParsedAnswerCandidate,
    parse_generation_final_output,
)
from backend.domain.validation.retry_policy import RetryPolicy
from backend.shared.errors.errors import ValidationResultFormatError
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
        max_retries: int,
        reference_file_validator: ReferenceFileValidatorPort,
        validator_codex_runner: ValidatorCodexRunnerPort,
        validator_max_retries: int = 0,
        artifact_link_validator: AnswerArtifactLinkValidator | None = None,
        retry_policy: RetryPolicy | None = None,
        validator_retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._reference_file_validator = reference_file_validator
        self._validator_codex_runner = validator_codex_runner
        self._retry_policy = (
            retry_policy if retry_policy is not None else RetryPolicy(max_retries)
        )
        self._validator_retry_policy = (
            validator_retry_policy
            if validator_retry_policy is not None
            else RetryPolicy(validator_max_retries)
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
        get_timeout_seconds: Callable[[], int] | None = None,
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

        validation = self._validate_references(
            candidate=candidate,
            user_instruction=user_instruction,
            chat_id=chat_id,
            run_id=run_id,
            trace_id=trace_id,
            get_timeout_seconds=get_timeout_seconds,
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

    def _validate_references(
        self,
        candidate: ParsedAnswerCandidate,
        user_instruction: str,
        chat_id: UUID | None,
        run_id: UUID | None,
        trace_id: str,
        get_timeout_seconds: Callable[[], int] | None,
        on_intermediate_message: Callable[[str], None] | None,
        session_workdir: Path | None,
        has_artifact_links: bool,
    ) -> ReferenceValidationResult:
        file_validation = self._reference_file_validator.validate_reference_files(
            candidate
        )
        if not file_validation.valid:
            return file_validation

        parsed = self._run_validator_codex_with_retry(
            candidate=candidate,
            user_instruction=user_instruction,
            chat_id=chat_id,
            run_id=run_id,
            trace_id=trace_id,
            get_timeout_seconds=get_timeout_seconds,
            on_intermediate_message=on_intermediate_message,
            session_workdir=session_workdir,
            has_artifact_links=has_artifact_links,
        )
        return ReferenceValidationResult(valid=parsed.valid, comment=parsed.comment)

    def _run_validator_codex_with_retry(
        self,
        candidate: ParsedAnswerCandidate,
        user_instruction: str,
        chat_id: UUID | None,
        run_id: UUID | None,
        trace_id: str,
        get_timeout_seconds: Callable[[], int] | None,
        on_intermediate_message: Callable[[str], None] | None,
        session_workdir: Path | None,
        has_artifact_links: bool,
    ) -> ParsedValidatorOutput:
        if chat_id is None or run_id is None:
            raise ValidationResultFormatError("検証対象の実行文脈が不正です。")
        prompt = build_validator_prompt(
            user_instruction=user_instruction,
            candidate=candidate,
        )
        format_retry_count = 0
        while True:
            result = self._validator_codex_runner.run_validation(
                chat_id=chat_id,
                run_id=run_id,
                prompt=prompt,
                timeout_seconds=_validation_timeout_seconds(
                    get_timeout_seconds=get_timeout_seconds,
                ),
                trace_id=trace_id,
                on_intermediate_message=on_intermediate_message,
                session_workdir=session_workdir,
                has_artifact_links=has_artifact_links,
            )
            try:
                return parse_validator_final_output(result.final_output_json)
            except ValidationResultFormatError:
                if not self._validator_retry_policy.can_retry(format_retry_count):
                    raise
                format_retry_count += 1
                prompt = build_validator_result_retry_prompt()

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


def _validation_timeout_seconds(
    *,
    get_timeout_seconds: Callable[[], int] | None,
) -> int:
    if get_timeout_seconds is not None:
        return get_timeout_seconds()
    return 0

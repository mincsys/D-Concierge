from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from backend.application.artifacts.links import (
    artifact_diagnostics,
    extract_artifact_links,
)
from backend.application.ports.codex.dto import ValidatorCodexRequest
from backend.application.ports.codex.interface import (
    ReferenceFileValidatorPort,
    ValidatorCodexRunnerPort,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


class ValidationStatus(StrEnum):
    """回答検証の結果種別。"""

    ACCEPTED = "accepted"
    REGENERATE = "regenerate"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ValidateAnswerCommand:
    """回答候補検証要求。"""

    chat_id: UUID
    run_id: UUID
    user_id: str
    session_id: UUID
    candidate_json: str
    artifacts_dir: Path
    retry_count: int
    max_regenerations: int
    remaining_seconds: int
    trace_id: str


@dataclass(frozen=True, slots=True)
class ValidatedReference:
    """固定検証済み参照元。"""

    source_type: str
    path: str
    page_start: int
    page_end: int


@dataclass(frozen=True, slots=True)
class ValidatedBlock:
    """固定検証済み回答ブロック。"""

    markdown: str
    references: tuple[ValidatedReference, ...]
    artifact_links: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    """採用可能な回答候補。"""

    blocks: tuple[ValidatedBlock, ...]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """回答検証結果。"""

    status: ValidationStatus
    answer: ValidatedAnswer | None = None
    regeneration_instruction: str | None = None
    diagnostic_message: str | None = None
    validation_conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class _FixedValidationResult:
    answer: ValidatedAnswer | None
    diagnostic_message: str | None = None


@dataclass(frozen=True, slots=True)
class _CandidateLocatorModel:
    path: str
    start_page: int
    end_page: int


@dataclass(frozen=True, slots=True)
class _CandidateReferenceModel:
    source_type: str
    locator: _CandidateLocatorModel


@dataclass(frozen=True, slots=True)
class _CandidateAnswerModel:
    text: str
    references: tuple[_CandidateReferenceModel, ...]


@dataclass(frozen=True, slots=True)
class _CandidateFinalPayloadModel:
    kind: str
    answers: tuple[_CandidateAnswerModel, ...]


@dataclass(frozen=True, slots=True)
class _CandidateEnvelopeModel:
    payload: _CandidateFinalPayloadModel


@dataclass(frozen=True, slots=True)
class _ValidatorFinalPayloadModel:
    kind: str
    valid: bool
    comment: str


@dataclass(frozen=True, slots=True)
class _ValidatorEnvelopeModel:
    payload: _ValidatorFinalPayloadModel


@dataclass(frozen=True, slots=True)
class _ParsedValidatorResult:
    conversation_id: str
    payload: _ValidatorFinalPayloadModel


@dataclass(frozen=True, slots=True)
class ValidateAnswerUseCase:
    """回答候補を固定検証とCodex検証へ通す。"""

    reference_validator: ReferenceFileValidatorPort
    validator_runner: ValidatorCodexRunnerPort
    validator_output_max_retries: int = 1

    def execute(self, command: ValidateAnswerCommand) -> ValidationResult:
        fixed_result = self._fixed_validate(command)
        if fixed_result.answer is None:
            diagnostic_message = (
                fixed_result.diagnostic_message or "回答候補の形式が不正です。"
            )
            return ValidationResult(
                status=ValidationStatus.REGENERATE,
                regeneration_instruction=_regeneration_instruction(diagnostic_message),
            )
        answer = fixed_result.answer
        validator_result = self._run_validator(command, answer)
        comment = validator_result.payload.comment
        if validator_result.payload.valid:
            return ValidationResult(
                status=ValidationStatus.ACCEPTED,
                answer=answer,
                validation_conversation_id=validator_result.conversation_id,
            )
        if command.retry_count >= command.max_regenerations:
            return ValidationResult(
                status=ValidationStatus.FAILED,
                diagnostic_message=comment,
                validation_conversation_id=validator_result.conversation_id,
            )
        return ValidationResult(
            status=ValidationStatus.REGENERATE,
            regeneration_instruction=_regeneration_instruction(comment),
            validation_conversation_id=validator_result.conversation_id,
        )

    def _fixed_validate(
        self,
        command: ValidateAnswerCommand,
    ) -> _FixedValidationResult:
        try:
            envelope = _candidate_envelope(command.candidate_json)
        except ValueError:
            return _FixedValidationResult(
                answer=None,
                diagnostic_message="payload.answers",
            )
        if not envelope.payload.answers:
            return _FixedValidationResult(
                answer=None,
                diagnostic_message="payload.answers",
            )
        blocks: list[ValidatedBlock] = []
        diagnostics: list[str] = []
        for answer_index, answer in enumerate(envelope.payload.answers):
            references = self._references(answer_index, answer, diagnostics)
            if not answer.text.strip():
                diagnostics.append(f"payload.answers[{answer_index}].text")
            artifact_links = extract_artifact_links(answer.text)
            diagnostics.extend(
                artifact_diagnostics(command.artifacts_dir, artifact_links),
            )
            if _contains_dangerous_html(answer.text):
                diagnostics.append("HTMLを含む回答本文は採用できません。")
            blocks.append(
                ValidatedBlock(
                    markdown=answer.text,
                    references=references,
                    artifact_links=tuple(link.relative_path for link in artifact_links),
                )
            )
        if diagnostics:
            return _FixedValidationResult(
                answer=None,
                diagnostic_message="; ".join(diagnostics),
            )
        return _FixedValidationResult(answer=ValidatedAnswer(blocks=tuple(blocks)))

    def _references(
        self,
        answer_index: int,
        answer: _CandidateAnswerModel,
        diagnostics: list[str],
    ) -> tuple[ValidatedReference, ...]:
        references: list[ValidatedReference] = []
        for reference_index, reference in enumerate(answer.references):
            diagnostic_prefix = (
                f"payload.answers[{answer_index}].references[{reference_index}]"
            )
            if reference.source_type != "pdf":
                diagnostics.append(
                    f"{diagnostic_prefix}.source_type はpdfだけ指定できます。",
                )
                continue
            normalized_path = _normalize_pdf_path(reference.locator.path)
            if normalized_path is None:
                diagnostics.append(
                    f"{diagnostic_prefix}.locator.path は"
                    "data_source配下のPDFが必要です: "
                    f"{reference.locator.path}",
                )
                continue
            page_start = reference.locator.start_page
            page_end = reference.locator.end_page
            if page_start <= 0 or page_end < page_start:
                diagnostics.append(
                    f"{diagnostic_prefix}.locator のページ範囲が不正です。",
                )
                continue
            validation = self.reference_validator.validate_pdf_reference(
                normalized_path,
                page_start,
                page_end,
            )
            if not validation.exists:
                diagnostics.append(
                    f"{diagnostic_prefix}.locator.path のPDFが存在しません: "
                    f"data_source/{normalized_path}",
                )
                continue
            if not validation.readable:
                raise AppError(
                    error_type=ErrorType.SYSTEM,
                    trace=True,
                    diagnostic_message=f"PDF読み取り失敗: {normalized_path}",
                )
            if page_end > validation.page_count:
                diagnostics.append(
                    f"{diagnostic_prefix}.locator.page_end が"
                    "PDFページ数を超えています。",
                )
                continue
            references.append(
                ValidatedReference(
                    source_type="pdf",
                    path=normalized_path,
                    page_start=page_start,
                    page_end=page_end,
                )
            )
        return tuple(references)

    def _run_validator(
        self,
        command: ValidateAnswerCommand,
        answer: ValidatedAnswer,
    ) -> _ParsedValidatorResult:
        resume_conversation_id: str | None = None
        attempts = self.validator_output_max_retries + 1
        artifacts_dir = command.artifacts_dir if _has_artifacts(answer) else None
        for _ in range(attempts):
            result = self.validator_runner.run_validation(
                ValidatorCodexRequest(
                    chat_id=command.chat_id,
                    run_id=command.run_id,
                    user_id=command.user_id,
                    session_id=command.session_id,
                    candidate_json=command.candidate_json,
                    resume_conversation_id=resume_conversation_id,
                    artifacts_readonly_dir=artifacts_dir,
                    remaining_seconds=command.remaining_seconds,
                )
            )
            resume_conversation_id = result.conversation_id
            try:
                envelope = _validator_envelope(result.final_result_json)
                return _ParsedValidatorResult(
                    conversation_id=result.conversation_id,
                    payload=envelope.payload,
                )
            except ValueError:
                continue
        raise AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="検証用Codexの最終出力形式が不正です。",
        )


def _candidate_envelope(text: str) -> _CandidateEnvelopeModel:
    value = _load_json(text)
    payload = _required_dict(value, "payload")
    kind = _required_str(payload, "kind")
    if kind != "final":
        raise ValueError("payload.kind")
    answers_value = _required_list(payload, "answers")
    answers: list[_CandidateAnswerModel] = []
    for answer_value in answers_value:
        answer = _as_dict(answer_value)
        text_value = _required_str(answer, "text")
        references_value = _required_list(answer, "references")
        references: list[_CandidateReferenceModel] = []
        for reference_value in references_value:
            reference = _as_dict(reference_value)
            locator = _required_dict(reference, "locator")
            references.append(
                _CandidateReferenceModel(
                    source_type=_required_str(reference, "source_type"),
                    locator=_CandidateLocatorModel(
                        path=_required_str(locator, "path"),
                        start_page=_required_int(locator, "start_page"),
                        end_page=_required_int(locator, "end_page"),
                    ),
                )
            )
        answers.append(
            _CandidateAnswerModel(
                text=text_value,
                references=tuple(references),
            )
        )
    return _CandidateEnvelopeModel(
        payload=_CandidateFinalPayloadModel(
            kind=kind,
            answers=tuple(answers),
        )
    )


def _validator_envelope(text: str) -> _ValidatorEnvelopeModel:
    value = _load_json(text)
    payload = _required_dict(value, "payload")
    kind = _required_str(payload, "kind")
    if kind != "final":
        raise ValueError("payload.kind")
    return _ValidatorEnvelopeModel(
        payload=_ValidatorFinalPayloadModel(
            kind=kind,
            valid=_required_bool(payload, "valid"),
            comment=_required_str(payload, "comment"),
        )
    )


def _load_json(text: str) -> JsonValue:
    try:
        value: JsonValue = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("json") from error
    return value


def _required_dict(value: JsonValue, key: str) -> dict[str, JsonValue]:
    parent = _as_dict(value)
    child = parent.get(key)
    if isinstance(child, dict):
        return child
    raise ValueError(key)


def _required_list(value: dict[str, JsonValue], key: str) -> list[JsonValue]:
    child = value.get(key)
    if isinstance(child, list):
        return child
    raise ValueError(key)


def _required_str(value: dict[str, JsonValue], key: str) -> str:
    child = value.get(key)
    if isinstance(child, str):
        return child
    raise ValueError(key)


def _required_int(value: dict[str, JsonValue], key: str) -> int:
    child = value.get(key)
    if isinstance(child, int) and not isinstance(child, bool):
        return child
    raise ValueError(key)


def _required_bool(value: dict[str, JsonValue], key: str) -> bool:
    child = value.get(key)
    if isinstance(child, bool):
        return child
    raise ValueError(key)


def _as_dict(value: JsonValue) -> dict[str, JsonValue]:
    if isinstance(value, dict):
        return value
    raise ValueError("dict")


def _normalize_pdf_path(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    if "://" in normalized or normalized.startswith(("/", "//")):
        return None
    if not normalized.startswith("data_source/"):
        return None
    relative = normalized.removeprefix("data_source/")
    path = Path(relative)
    if ".." in path.parts or path.suffix.lower() != ".pdf":
        return None
    return relative


def _contains_dangerous_html(markdown: str) -> bool:
    lowered = markdown.lower()
    return (
        "<" in markdown
        and ">" in markdown
        and ("onerror" in lowered or "<script" in lowered)
    )


def _has_artifacts(answer: ValidatedAnswer) -> bool:
    return any(block.artifact_links for block in answer.blocks)


def _regeneration_instruction(message: str) -> str:
    return f"不合格理由: {message}"

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pypdf import PdfReader

from backend.application.ports.codex.dto import ReferenceValidationResult
from backend.application.ports.database.interface import (
    ChatRuntimeRepositoryPort,
    TransactionManagerPort,
)
from backend.application.transactions import NoopTransactionManager
from backend.domain.answer.answer_candidate import (
    InvalidPageRange,
    ParsedAnswerCandidate,
    ParsedReference,
    codex_visible_reference_path,
    invalid_reference_page_range_message,
    invalid_reference_path_message,
    parsed_candidate_references,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.intermediate_messages import (
    CodexIntermediateMessageStreamer,
)
from backend.infrastructure.codex.jsonl_event_parser import JsonValue
from backend.infrastructure.codex.session_readonly import (
    prepare_validation_session_artifacts,
    prepare_validation_session_readonly,
)
from backend.infrastructure.codex.validator_codex_input import (
    build_validator_codex_input,
)
from backend.infrastructure.config.models import CodexConfig
from backend.infrastructure.filesystem.path_security import PathSecurityService
from backend.shared.errors import (
    AppError,
    ErrorClass,
    ReferencePdfReadError,
    ValidationResultFormatError,
    ValidationWorkspacePreparationError,
)


class InfrastructureCodexRunner(Protocol):
    """実CodexRunnerの検証実行境界。"""

    def run_validation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """検証用codex execを実行する。"""


@dataclass(frozen=True, slots=True)
class _ParsedValidationResult:
    valid: bool
    comment: str


class CodexReferenceValidator:
    """検証用CodexRunnerを参照元検証境界へ適合させる。"""

    def __init__(
        self,
        repository: ChatRuntimeRepositoryPort,
        codex_runner: InfrastructureCodexRunner,
        validator_config: CodexConfig,
        datasource_dir: Path,
        timeout_seconds: int,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        self._repository = repository
        self._codex_runner = codex_runner
        self._validator_config = validator_config
        self._datasource_dir = datasource_dir
        self._timeout_seconds = timeout_seconds
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def validate_references(
        self,
        candidate: ParsedAnswerCandidate,
        user_instruction: str,
        chat_id: UUID | None = None,
        run_id: UUID | None = None,
        trace_id: str = "",
        timeout_seconds: int | None = None,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
        has_artifact_links: bool = False,
    ) -> ReferenceValidationResult:
        """検証用codex execで回答候補の参照元妥当性を検証する。"""
        if chat_id is None or run_id is None:
            raise AppError(ErrorClass.SYSTEM, "検証対象の実行文脈が不正です。")

        with self._transaction_manager.transaction():
            context = self._repository.get_chat_runtime_context(chat_id)
        workdir = (
            self._validator_config.workdir
            / str(context.local_user_id)
            / str(context.session_id)
        )
        local_validation = _validate_reference_files(
            references=parsed_candidate_references(candidate),
            datasource_dir=self._datasource_dir,
        )
        if local_validation is not None:
            return local_validation

        prepare_validation_session_readonly(
            workdir=workdir,
            datasource_dir=self._datasource_dir,
        )
        if has_artifact_links:
            if session_workdir is None:
                raise ValidationWorkspacePreparationError(
                    "生成成果物ディレクトリを検証用作業領域へ提示できません。",
                )
            prepare_validation_session_artifacts(
                validation_workdir=workdir,
                generation_workdir=session_workdir,
                has_artifact_links=True,
            )
        intermediate_streamer = CodexIntermediateMessageStreamer(
            on_intermediate_message
        )
        result = self._codex_runner.run_validation(
            CodexRunRequest(
                run_id=run_id,
                prompt=_validation_prompt(
                    candidate=candidate,
                    user_instruction=user_instruction,
                ),
                codex_home=self._validator_config.home,
                workdir=workdir,
                output_schema=self._validator_config.output_schema,
                codex_conversation_id=context.validation_conversation_id,
                timeout_seconds=(
                    timeout_seconds
                    if timeout_seconds is not None
                    else self._timeout_seconds
                ),
                trace_id=trace_id,
                on_event=intermediate_streamer.accept
                if on_intermediate_message is not None
                else None,
            )
        )
        with self._transaction_manager.transaction():
            self._repository.save_validation_conversation_id(
                chat_id,
                result.codex_conversation_id,
            )
        parsed = _parse_validation_result(result.final_message)
        return ReferenceValidationResult(
            valid=parsed.valid,
            comment=parsed.comment,
        )


def _validation_prompt(
    *,
    candidate: ParsedAnswerCandidate,
    user_instruction: str,
) -> str:
    return json.dumps(
        build_validator_codex_input(
            user_instruction=user_instruction,
            candidate=candidate,
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _parse_validation_result(raw_json: str) -> _ParsedValidationResult:
    try:
        loaded: JsonValue = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValidationResultFormatError("検証結果を解析できませんでした。") from exc
    if not isinstance(loaded, dict):
        raise ValidationResultFormatError("検証結果の形式が不正です。")

    payload = loaded.get("payload")
    if not isinstance(payload, dict) or payload.get("kind") != "final":
        raise ValidationResultFormatError("検証結果の形式が不正です。")
    valid_value = payload.get("valid")
    comment_value = payload.get("comment")
    if not isinstance(valid_value, bool) or not isinstance(comment_value, str):
        raise ValidationResultFormatError("検証結果の形式が不正です。")
    return _ParsedValidationResult(valid=valid_value, comment=comment_value)


def _validate_reference_files(
    references: tuple[ParsedReference, ...],
    datasource_dir: Path,
) -> ReferenceValidationResult | None:
    invalid_paths: list[str] = []
    resolved_paths: dict[str, Path] = {}
    for reference in references:
        display_path = codex_visible_reference_path(reference.relative_path)
        try:
            resolved_path = PathSecurityService.resolve_file(
                datasource_dir,
                reference.relative_path,
                (".pdf",),
            )
        except AppError:
            invalid_paths.append(display_path)
            continue
        if not resolved_path.is_file():
            invalid_paths.append(display_path)
            continue
        resolved_paths[reference.relative_path] = resolved_path

    if invalid_paths:
        return ReferenceValidationResult(
            valid=False,
            comment=invalid_reference_path_message(invalid_paths),
        )

    page_counts: dict[str, int] = {}
    invalid_page_ranges: list[InvalidPageRange] = []
    for reference in references:
        page_count = page_counts.get(reference.relative_path)
        if page_count is None:
            try:
                resolved_path = resolved_paths[reference.relative_path]
                page_count = len(PdfReader(str(resolved_path)).pages)
            except Exception as exc:  # noqa: BLE001
                raise ReferencePdfReadError(reference.relative_path, exc) from exc
            page_counts[reference.relative_path] = page_count

        if reference.page_end > page_count:
            invalid_page_ranges.append(
                InvalidPageRange(
                    path=codex_visible_reference_path(reference.relative_path),
                    page_start=reference.page_start,
                    page_end=reference.page_end,
                ),
            )
    if invalid_page_ranges:
        return ReferenceValidationResult(
            valid=False,
            comment=invalid_reference_page_range_message(invalid_page_ranges),
        )
    return None

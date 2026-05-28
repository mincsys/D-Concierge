from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pypdf import PdfReader

from backend.application.ports.codex.dto import (
    ReferenceValidationResult,
    ValidatorCodexRunResult,
)
from backend.application.ports.database.interface import (
    ChatRuntimeRepositoryPort,
    TransactionManagerPort,
)
from backend.domain.answer.answer_candidate import (
    InvalidPageRange,
    InvalidReferencePageRangeFailure,
    InvalidReferencePathFailure,
    ParsedAnswerCandidate,
    parsed_candidate_references,
)
from backend.domain.references.pdf_reference import PdfReference
from backend.infrastructure.codex.codex_runner import (
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.intermediate_messages import (
    CodexIntermediateMessageStreamer,
)
from backend.infrastructure.codex.session_readonly import (
    prepare_validation_session_artifacts,
    prepare_validation_session_readonly,
)
from backend.infrastructure.config.models import ValidatorConfig
from backend.infrastructure.filesystem.path_security import PathSecurityService
from backend.shared.errors.errors import (
    AppError,
    ReferencePdfReadError,
    ValidationWorkspacePreparationError,
)


class InfrastructureCodexRunner(Protocol):
    """実CodexRunnerの検証実行境界。"""

    def run_validation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        """検証用codex execを実行する。"""


class CodexReferenceFileValidator:
    """参照元PDFファイル固定検証境界へ実ファイル検証を適合させる。"""

    def __init__(self, datasource_dir: Path) -> None:
        self._datasource_dir = datasource_dir

    def validate_reference_files(
        self,
        candidate: ParsedAnswerCandidate,
    ) -> ReferenceValidationResult:
        """回答候補の参照元PDFファイルとページ範囲を固定検証する。"""
        validation = _validate_reference_files(
            references=parsed_candidate_references(candidate),
            datasource_dir=self._datasource_dir,
        )
        if validation is not None:
            return validation
        return ReferenceValidationResult(valid=True)


class CodexValidationRunnerAdapter:
    """検証用CodexRunnerを1回実行境界へ適合させる。"""

    def __init__(
        self,
        repository: ChatRuntimeRepositoryPort,
        codex_runner: InfrastructureCodexRunner,
        validator_config: ValidatorConfig,
        datasource_dir: Path,
        timeout_seconds: int,
        transaction_manager: TransactionManagerPort,
    ) -> None:
        self._repository = repository
        self._codex_runner = codex_runner
        self._validator_config = validator_config
        self._datasource_dir = datasource_dir
        self._timeout_seconds = timeout_seconds
        self._transaction_manager = transaction_manager

    def run_validation(
        self,
        chat_id: UUID,
        run_id: UUID,
        prompt: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
        has_artifact_links: bool = False,
    ) -> ValidatorCodexRunResult:
        """検証用codex execを1回実行し、rawな最終出力を返す。"""
        with self._transaction_manager.transaction():
            context = self._repository.get_chat_runtime_context(chat_id)
        workdir = (
            self._validator_config.workdir / context.user_id / str(context.session_id)
        )

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
                prompt=prompt,
                codex_home=self._validator_config.home,
                workdir=workdir,
                output_schema=self._validator_config.output_schema,
                codex_conversation_id=context.validation_conversation_id,
                timeout_seconds=timeout_seconds,
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
        return ValidatorCodexRunResult(
            conversation_id=result.codex_conversation_id,
            intermediate_messages=(
                ()
                if on_intermediate_message is not None
                else _intermediate_messages(result)
            ),
            final_output_json=result.final_message,
        )


def _intermediate_messages(
    result: InfrastructureCodexRunResult,
) -> tuple[str, ...]:
    agent_messages: list[str] = []
    intermediate_streamer = CodexIntermediateMessageStreamer(agent_messages.append)
    for event in result.events:
        intermediate_streamer.accept(event)
    return tuple(agent_messages)


def _validate_reference_files(
    references: tuple[PdfReference, ...],
    datasource_dir: Path,
) -> ReferenceValidationResult | None:
    invalid_paths: list[str] = []
    resolved_paths: dict[str, Path] = {}
    for reference in references:
        display_path = reference.codex_visible_path()
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
            failure=InvalidReferencePathFailure(tuple(invalid_paths)),
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
                    path=reference.codex_visible_path(),
                    page_start=reference.page_start,
                    page_end=reference.page_end,
                ),
            )
    if invalid_page_ranges:
        return ReferenceValidationResult(
            valid=False,
            failure=InvalidReferencePageRangeFailure(tuple(invalid_page_ranges)),
        )
    return None

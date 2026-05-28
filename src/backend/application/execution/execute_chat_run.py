from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path
from typing import Protocol
from uuid import UUID

from backend.application.artifacts.save_adopted_artifacts import (
    SavedAnswerBlocksArtifacts,
)
from backend.application.execution.generation_prompt import build_generation_prompt
from backend.application.execution.run_event_type import RunEventType
from backend.application.ports.codex.interface import (
    CodexGenerationRunnerPort,
    SessionWorkdirResolverPort,
)
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    DisplayReferenceData,
)
from backend.application.ports.database.interface import (
    ChatExecutionRepositoryPort,
    TransactionManagerPort,
)
from backend.application.ports.runtime.interface import ClockPort, IdGeneratorPort
from backend.application.ports.trace_log.dto import TraceLogRecord
from backend.application.ports.trace_log.interface import TraceLoggerPort
from backend.application.transactions import NoopTransactionManager
from backend.application.validation.validate_answer import (
    AnswerValidationResult,
)
from backend.application.validation.validation_status import ValidationStatus
from backend.domain.answer.answer_candidate import (
    ParsedAnswerCandidate,
)
from backend.domain.execution.run_state import RunState
from backend.domain.references.pdf_reference import PdfLocator, PdfReference
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import (
    AppError,
    CodexProcessFailureError,
    CodexProviderError,
    ProcessCanceledConflictError,
    ReferencePdfReadError,
    RunStateChangedError,
    RunTimeoutError,
    ValidationResultFormatError,
    ValidationWorkspacePreparationError,
)
from backend.shared.tracing.exception import exception_message, exception_stacktrace
from backend.shared.user_messages import (
    AI_PROVIDER_FAILURE_MESSAGE,
    ANSWER_REVISION_MESSAGE,
    ANSWER_VALIDATION_FAILED_MESSAGE,
    CANCELED_MESSAGE,
    GENERATION_FAILURE_MESSAGE,
    PDF_READ_FAILURE_MESSAGE,
    TIMEOUT_FAILURE_MESSAGE,
    UNEXPECTED_FAILURE_MESSAGE,
    VALIDATION_COMPLETED_MESSAGE,
    VALIDATION_RESULT_FAILURE_MESSAGE,
    VALIDATION_STARTED_MESSAGE,
    WORK_COMPLETED_MESSAGE,
    WORK_STARTED_MESSAGE,
)


@dataclass(frozen=True, slots=True)
class RunEvent:
    """run ID単位で発行するSSE向けイベント。"""

    event: RunEventType
    chat_id: UUID
    run_id: UUID
    state: RunState | None = None
    text: str | None = None
    answer: AnswerData | None = None
    user_message: str | None = None


class RunEventPublisher(Protocol):
    """runイベント発行境界。"""

    def publish(self, event: RunEvent) -> None:
        """イベントを発行する。"""


class AnswerValidator(Protocol):
    """回答候補の検証境界。"""

    def validate(
        self,
        raw_answer_json: str,
        retry_count: int,
        user_instruction: str,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        get_timeout_seconds: Callable[[], int],
        on_intermediate_message: Callable[[str], None] | None = None,
        session_workdir: Path | None = None,
    ) -> AnswerValidationResult:
        """回答候補を検証し、採用可否を返す。"""


class AdoptedArtifactSaver(Protocol):
    """採用済み回答の成果物保存境界。"""

    def save_for_answer_blocks(
        self,
        markdowns: tuple[str, ...],
        session_workdir: Path,
        trace_id: str,
    ) -> SavedAnswerBlocksArtifacts:
        """回答本文内の成果物参照を保存済みURLへ置換する。"""


class ExecuteChatRunUseCase:
    """受付済みrunの生成、固定検証、回答保存、イベント発行を調停する。"""

    def __init__(
        self,
        repository: ChatExecutionRepositoryPort,
        codex_runner: CodexGenerationRunnerPort,
        answer_validator: AnswerValidator,
        event_publisher: RunEventPublisher,
        clock: ClockPort,
        id_generator: IdGeneratorPort,
        artifact_saver: AdoptedArtifactSaver | None = None,
        session_workdir: Path | None = None,
        session_workdir_resolver: SessionWorkdirResolverPort | None = None,
        trace_logger: TraceLoggerPort | None = None,
        timeout_seconds: int = 300,
        transaction_manager: TransactionManagerPort | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_secondsは1以上である必要があります。")
        self._repository = repository
        self._codex_runner = codex_runner
        self._answer_validator = answer_validator
        self._event_publisher = event_publisher
        self._artifact_saver = artifact_saver
        self._session_workdir = session_workdir
        self._session_workdir_resolver = session_workdir_resolver
        self._trace_logger = trace_logger
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._id_generator = id_generator
        self._transaction_manager = (
            transaction_manager
            if transaction_manager is not None
            else NoopTransactionManager()
        )

    def execute(self, chat_id: UUID, run_id: UUID, trace_id: str = "") -> None:
        """受付済みrunを実行し、完了またはエラーへ終端する。"""
        execution_deadline_at = self._clock.now() + timedelta(
            seconds=self._timeout_seconds
        )
        try:
            self._execute(chat_id, run_id, trace_id, execution_deadline_at)
        except RunTimeoutError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_timeout(chat_id, run_id)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_timeout",
                    stage="execution",
                    chat_id=chat_id,
                    run_id=run_id,
                    exception_type=type(exc).__name__,
                    run_state=RunState.TIMED_OUT.value,
                    execution_deadline_at=execution_deadline_at,
                    timeout_state="codex_exec_timeout",
                    stacktrace=exception_stacktrace(exc),
                    message="Codex実行がタイムアウトしました。",
                )
            )
        except ReferencePdfReadError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_error(chat_id, run_id, PDF_READ_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage="validation",
                    chat_id=chat_id,
                    run_id=run_id,
                    error_type=exc.error_type.value,
                    exception_type=type(exc).__name__,
                    run_state=RunState.ERROR.value,
                    validation_failure_reason=exc.diagnostic_message,
                    stacktrace=exception_stacktrace(exc),
                    message=exc.diagnostic_message,
                )
            )
        except ValidationWorkspacePreparationError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_error(chat_id, run_id, UNEXPECTED_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage="validation",
                    chat_id=chat_id,
                    run_id=run_id,
                    error_type=exc.error_type.value,
                    exception_type=type(exc).__name__,
                    run_state=RunState.ERROR.value,
                    validation_failure_reason=exc.diagnostic_message,
                    stacktrace=exception_stacktrace(exc),
                    message=exc.diagnostic_message,
                )
            )
        except ValidationResultFormatError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_error(chat_id, run_id, VALIDATION_RESULT_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage="validation",
                    chat_id=chat_id,
                    run_id=run_id,
                    error_type=exc.error_type.value,
                    exception_type=type(exc).__name__,
                    run_state=RunState.ERROR.value,
                    validation_failure_reason=exc.diagnostic_message,
                    stacktrace=exception_stacktrace(exc),
                    message=exc.diagnostic_message,
                )
            )
        except CodexProviderError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_error(chat_id, run_id, AI_PROVIDER_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage=exc.stage,
                    chat_id=chat_id,
                    run_id=run_id,
                    error_type=exc.error_type.value,
                    exception_type=type(exc).__name__,
                    run_state=RunState.ERROR.value,
                    stacktrace=exception_stacktrace(exc),
                    process_result=exc.codex_message or "(messageなし)",
                    message=exc.diagnostic_message,
                )
            )
        except CodexProcessFailureError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_error(chat_id, run_id, UNEXPECTED_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage=exc.stage,
                    chat_id=chat_id,
                    run_id=run_id,
                    error_type=exc.error_type.value,
                    exception_type=type(exc).__name__,
                    run_state=RunState.ERROR.value,
                    stacktrace=exception_stacktrace(exc),
                    codex_exit_status=str(exc.return_code),
                    process_result=exc.stderr.strip() or "(stderrなし)",
                    message=exc.diagnostic_message,
                )
            )
        except AppError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_error(chat_id, run_id, GENERATION_FAILURE_MESSAGE)
            if exc.trace:
                self._write_trace(
                    TraceLogRecord(
                        trace_id=trace_id,
                        event_name="execution_failed",
                        stage="generation",
                        chat_id=chat_id,
                        run_id=run_id,
                        error_type=exc.error_type.value,
                        exception_type=type(exc).__name__,
                        run_state=RunState.ERROR.value,
                        stacktrace=exception_stacktrace(exc),
                        message=exc.diagnostic_message,
                    )
                )
        except Exception as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return
            self._finish_error(chat_id, run_id, UNEXPECTED_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage="execution",
                    chat_id=chat_id,
                    run_id=run_id,
                    error_type=ErrorType.SYSTEM.value,
                    exception_type=type(exc).__name__,
                    run_state=RunState.ERROR.value,
                    stacktrace=exception_stacktrace(exc),
                    message=exception_message(exc),
                )
            )

    def _execute(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        execution_deadline_at: datetime,
    ) -> None:
        with self._transaction_manager.transaction():
            user_instruction = self._repository.get_run_instruction(chat_id, run_id)
        if self._is_canceled(chat_id, run_id):
            self._finish_canceled(chat_id, run_id)
            return

        prompt = build_generation_prompt(user_instruction)
        retry_count = 0
        while True:
            generation_timeout_seconds = self._remaining_seconds(execution_deadline_at)
            self._change_state(
                chat_id,
                run_id,
                RunState.RUNNING,
                expected_states=(
                    (RunState.ACCEPTED,) if retry_count == 0 else (RunState.VALIDATING,)
                ),
                execution_deadline_at=(
                    execution_deadline_at if retry_count == 0 else None
                ),
            )
            self._record_intermediate_message(
                chat_id,
                run_id,
                WORK_STARTED_MESSAGE if retry_count == 0 else ANSWER_REVISION_MESSAGE,
            )
            result = self._codex_runner.run_generation(
                chat_id,
                run_id,
                prompt,
                timeout_seconds=generation_timeout_seconds,
                trace_id=trace_id,
                on_intermediate_message=lambda message: (
                    self._record_intermediate_message(chat_id, run_id, message)
                ),
            )
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return

            for message in result.intermediate_messages:
                self._record_intermediate_message(chat_id, run_id, message)
            self._record_intermediate_message(chat_id, run_id, WORK_COMPLETED_MESSAGE)
            self._change_state(
                chat_id,
                run_id,
                RunState.VALIDATING,
                expected_states=(RunState.RUNNING,),
            )
            self._record_intermediate_message(
                chat_id, run_id, VALIDATION_STARTED_MESSAGE
            )
            session_workdir = self._resolve_session_workdir(chat_id)
            validation = self._answer_validator.validate(
                result.final_answer_json,
                retry_count,
                user_instruction,
                chat_id,
                run_id,
                trace_id,
                get_timeout_seconds=lambda: self._remaining_seconds(
                    execution_deadline_at
                ),
                on_intermediate_message=lambda message: (
                    self._record_intermediate_message(chat_id, run_id, message)
                ),
                session_workdir=session_workdir,
            )
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return

            match validation.status:
                case ValidationStatus.ACCEPTED:
                    if validation.candidate is None:
                        self._finish_error(
                            chat_id, run_id, ANSWER_VALIDATION_FAILED_MESSAGE
                        )
                        return
                    self._record_intermediate_message(
                        chat_id, run_id, VALIDATION_COMPLETED_MESSAGE
                    )
                    self._save_answer(
                        chat_id,
                        run_id,
                        validation.candidate,
                        trace_id,
                    )
                    return
                case ValidationStatus.REGENERATE:
                    retry_count += 1
                    prompt = build_generation_prompt(
                        user_instruction,
                        validation.regeneration_instruction,
                    )
                case ValidationStatus.FAILED:
                    self._write_trace(
                        TraceLogRecord(
                            trace_id=trace_id,
                            event_name="validation_retry_limit_reached",
                            stage="validation",
                            chat_id=chat_id,
                            run_id=run_id,
                            error_type=ErrorType.SYSTEM.value,
                            run_state=RunState.ERROR.value,
                            retry_count=retry_count,
                            validation_failure_reason=(
                                validation.regeneration_instruction
                                or validation.user_message
                                or "回答検証の最大試行回数に到達しました。"
                            ),
                            validation_comment=validation.regeneration_instruction
                            or None,
                            message=(
                                validation.regeneration_instruction
                                or "回答検証の最大試行回数に到達しました。"
                            ),
                        )
                    )
                    self._finish_error(
                        chat_id,
                        run_id,
                        validation.user_message or ANSWER_VALIDATION_FAILED_MESSAGE,
                    )
                    return

    def _change_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        expected_states: tuple[RunState, ...],
        execution_deadline_at: datetime | None = None,
    ) -> None:
        with self._transaction_manager.transaction():
            updated = self._repository.update_run_state_if_current(
                chat_id=chat_id,
                run_id=run_id,
                expected_states=expected_states,
                state=state,
                execution_deadline_at=execution_deadline_at,
            )
        if not updated:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                raise ProcessCanceledConflictError()
            raise RunStateChangedError()
        self._event_publisher.publish(
            RunEvent(
                event=RunEventType.STATE,
                chat_id=chat_id,
                run_id=run_id,
                state=state,
            )
        )

    def _record_intermediate_message(
        self, chat_id: UUID, run_id: UUID, message: str
    ) -> None:
        with self._transaction_manager.transaction():
            self._repository.add_intermediate_message(chat_id, run_id, message)
        self._event_publisher.publish(
            RunEvent(
                event=RunEventType.MESSAGE,
                chat_id=chat_id,
                run_id=run_id,
                text=message,
            )
        )

    def _save_answer(
        self,
        chat_id: UUID,
        run_id: UUID,
        candidate: ParsedAnswerCandidate,
        trace_id: str,
    ) -> None:
        markdowns = tuple(block.markdown for block in candidate.blocks)
        block_artifacts: tuple[tuple[ArtifactData, ...], ...] = tuple(
            () for _block in candidate.blocks
        )
        if self._artifact_saver is not None:
            session_workdir = self._resolve_session_workdir(chat_id)
            if session_workdir is None:
                self._finish_error(chat_id, run_id, "回答を検証できませんでした。")
                return
            saved = self._artifact_saver.save_for_answer_blocks(
                markdowns=markdowns,
                session_workdir=session_workdir,
                trace_id=trace_id,
            )
            markdowns = tuple(block.markdown for block in saved.blocks)
            block_artifacts = tuple(
                tuple(
                    ArtifactData(
                        artifact_id=artifact.artifact_id,
                        mime_type=artifact.mime_type,
                        relative_path=artifact.relative_path,
                    )
                    for artifact in block.artifacts
                )
                for block in saved.blocks
            )

        answer = AnswerData(
            blocks=tuple(
                AnswerBlockData(
                    markdown=markdown,
                    references=tuple(
                        DisplayReferenceData(
                            reference_id=self._id_generator.new_uuid(),
                            source_type=reference.source_type,
                            label=reference.label,
                            relative_path=reference.relative_path,
                            page_start=reference.page_start,
                            page_end=reference.page_end,
                        )
                        for reference in _merge_references(block.references)
                    ),
                    artifacts=artifacts,
                )
                for markdown, block, artifacts in zip(
                    markdowns, candidate.blocks, block_artifacts, strict=True
                )
            ),
        )
        with self._transaction_manager.transaction():
            self._repository.save_completed_answer(chat_id, run_id, answer)
            self._repository.set_run_state(chat_id, run_id, RunState.COMPLETED)
        self._event_publisher.publish(
            RunEvent(
                event=RunEventType.ANSWER,
                chat_id=chat_id,
                run_id=run_id,
                state=RunState.COMPLETED,
                answer=answer,
            )
        )

    def _resolve_session_workdir(self, chat_id: UUID) -> Path | None:
        if self._session_workdir_resolver is not None:
            with self._transaction_manager.transaction():
                return self._session_workdir_resolver.resolve_generation_workdir(
                    chat_id
                )
        return self._session_workdir

    def _finish_error(self, chat_id: UUID, run_id: UUID, user_message: str) -> None:
        with self._transaction_manager.transaction():
            updated = self._repository.update_run_state_if_current(
                chat_id=chat_id,
                run_id=run_id,
                expected_states=(
                    RunState.ACCEPTED,
                    RunState.RUNNING,
                    RunState.VALIDATING,
                ),
                state=RunState.ERROR,
                user_message=user_message,
            )
        if not updated:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
            return
        self._event_publisher.publish(
            RunEvent(
                event=RunEventType.ERROR,
                chat_id=chat_id,
                run_id=run_id,
                state=RunState.ERROR,
                user_message=user_message,
            )
        )

    def _finish_timeout(self, chat_id: UUID, run_id: UUID) -> None:
        with self._transaction_manager.transaction():
            updated = self._repository.update_run_state_if_current(
                chat_id=chat_id,
                run_id=run_id,
                expected_states=(
                    RunState.ACCEPTED,
                    RunState.RUNNING,
                    RunState.VALIDATING,
                ),
                state=RunState.TIMED_OUT,
                user_message=TIMEOUT_FAILURE_MESSAGE,
            )
        if not updated:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
            return
        self._event_publisher.publish(
            RunEvent(
                event=RunEventType.ERROR,
                chat_id=chat_id,
                run_id=run_id,
                state=RunState.TIMED_OUT,
                user_message=TIMEOUT_FAILURE_MESSAGE,
            )
        )

    def _finish_canceled(self, chat_id: UUID, run_id: UUID) -> None:
        with self._transaction_manager.transaction():
            self._repository.update_run_state_if_current(
                chat_id=chat_id,
                run_id=run_id,
                expected_states=(
                    RunState.ACCEPTED,
                    RunState.RUNNING,
                    RunState.VALIDATING,
                    RunState.CANCEL_REQUESTED,
                ),
                state=RunState.CANCELED,
                user_message=CANCELED_MESSAGE,
            )
        self._event_publisher.publish(
            RunEvent(
                event=RunEventType.CANCELED,
                chat_id=chat_id,
                run_id=run_id,
                state=RunState.CANCELED,
                user_message=CANCELED_MESSAGE,
            )
        )

    def _is_canceled(self, chat_id: UUID, run_id: UUID) -> bool:
        with self._transaction_manager.transaction():
            return self._repository.get_run_state(chat_id, run_id) in {
                RunState.CANCEL_REQUESTED,
                RunState.CANCELED,
            }

    def _remaining_seconds(self, execution_deadline_at: datetime) -> int:
        remaining = (execution_deadline_at - self._clock.now()).total_seconds()
        if remaining <= 0:
            raise RunTimeoutError()
        return max(1, ceil(remaining))

    def _write_trace(self, record: TraceLogRecord) -> None:
        if self._trace_logger is not None:
            self._trace_logger.write(record)


def _merge_references(
    references: tuple[PdfReference, ...],
) -> tuple[PdfReference, ...]:
    sorted_references = sorted(
        references,
        key=lambda reference: (
            reference.relative_path,
            reference.page_start,
            reference.page_end,
        ),
    )
    merged: list[PdfReference] = []
    for reference in sorted_references:
        if not merged:
            merged.append(reference)
            continue

        current = merged[-1]
        if (
            current.relative_path == reference.relative_path
            and reference.page_start <= current.page_end + 1
        ):
            merged[-1] = PdfReference(
                label=current.label,
                locator=PdfLocator(
                    relative_path=current.relative_path,
                    page_start=current.page_start,
                    page_end=max(current.page_end, reference.page_end),
                ),
            )
            continue

        merged.append(reference)
    return tuple(merged)

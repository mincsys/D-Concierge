from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import Protocol
from uuid import UUID, uuid7

from backend.application.artifacts.save_adopted_artifacts import (
    SaveAdoptedArtifactsCommand,
)
from backend.application.ports.codex.dto import CodexGenerationRequest
from backend.application.ports.database.dto import (
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    ChatRuntimeContext,
    DisplayReferenceData,
)
from backend.application.validation.validate_answer import (
    ValidateAnswerCommand,
    ValidationStatus,
)
from backend.domain.execution.run_state import RunState
from backend.shared.errors.errors import AppError

_EXECUTION_DEADLINE_SECONDS = 600
_VALIDATION_ERROR_MESSAGE = "回答の検証に失敗しました。"
_PDF_READ_ERROR_MESSAGE = "PDF読み取り中にエラーが発生しました。"
_UNEXPECTED_ERROR_MESSAGE = (
    "予期しないエラーが発生しました。開発者にお問い合わせください。"
)


@dataclass(frozen=True, slots=True)
class ExecuteChatRunCommand:
    """チャット実行要求。"""

    chat_id: UUID
    run_id: UUID
    trace_id: str


class ChatExecutionRepositoryLike(Protocol):
    """チャット実行ユースケースが必要とするRepository境界。"""

    def load_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext | None: ...

    def mark_run_running(
        self,
        run_id: UUID,
        execution_deadline_at: datetime,
    ) -> None: ...

    def mark_run_validating(self, run_id: UUID) -> None: ...

    def mark_run_completed(self, run_id: UUID) -> None: ...

    def mark_run_error(self, run_id: UUID, diagnostic_message: str) -> None: ...

    def mark_run_timed_out(self, run_id: UUID) -> None: ...

    def save_intermediate_message(self, run_id: UUID, text: str) -> None: ...

    def save_conversation_ids(
        self,
        chat_id: UUID,
        generation_conversation_id: str | None,
        validation_conversation_id: str | None,
    ) -> None: ...

    def save_answers(self, run_id: UUID, answers: tuple[AnswerData, ...]) -> None: ...


class TransactionManagerLike(Protocol):
    """DBトランザクション境界。"""

    def __enter__(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class GenerationRunnerLike(Protocol):
    """生成用Codex実行境界。"""

    def run_generation(
        self,
        request: CodexGenerationRequest,
    ) -> GenerationResultLike: ...


class GenerationResultLike(Protocol):
    """生成用Codex実行結果の参照項目。"""

    @property
    def conversation_id(self) -> str: ...

    @property
    def progress_messages(self) -> tuple[str, ...]: ...

    @property
    def final_answer_json(self) -> str: ...

    @property
    def artifacts_dir(self) -> Path: ...


class AnswerValidatorLike(Protocol):
    """回答検証境界。"""

    def execute(self, command: ValidateAnswerCommand) -> ValidationResultLike: ...


class ValidationResultLike(Protocol):
    """回答検証結果の参照項目。"""

    @property
    def status(self) -> ValidationStatus | str: ...

    @property
    def answer(self) -> ValidatedAnswerLike | None: ...

    @property
    def regeneration_instruction(self) -> str | None: ...

    @property
    def diagnostic_message(self) -> str | None: ...

    @property
    def validation_conversation_id(self) -> str | None: ...


class AdoptedArtifactSaverLike(Protocol):
    """採用済み成果物保存境界。"""

    def execute(
        self,
        command: SaveAdoptedArtifactsCommand,
    ) -> SavedArtifactsResultLike: ...


class SavedArtifactMetadataLike(Protocol):
    """保存済み成果物メタ情報の参照項目。"""

    @property
    def artifact_id(self) -> str | UUID: ...

    @property
    def storage_path(self) -> str: ...

    @property
    def public_url(self) -> str: ...

    @property
    def mime_type(self) -> str: ...


class SavedArtifactBlockLike(Protocol):
    """成果物リンク置換後ブロックの参照項目。"""

    @property
    def markdown(self) -> str: ...

    @property
    def artifacts(self) -> tuple[SavedArtifactMetadataLike, ...]: ...


class SavedArtifactsResultLike(Protocol):
    """採用済み成果物保存結果の参照項目。"""

    @property
    def blocks(self) -> tuple[SavedArtifactBlockLike, ...]: ...


class ValidatedReferenceLike(Protocol):
    """検証済み参照元の参照項目。"""

    @property
    def source_type(self) -> str: ...

    @property
    def path(self) -> str: ...

    @property
    def page_start(self) -> int: ...

    @property
    def page_end(self) -> int: ...


class ValidatedBlockLike(Protocol):
    """検証済み回答ブロックの参照項目。"""

    @property
    def markdown(self) -> str: ...

    @property
    def references(self) -> tuple[ValidatedReferenceLike, ...]: ...


class ValidatedAnswerLike(Protocol):
    """検証済み回答の参照項目。"""

    @property
    def blocks(self) -> tuple[ValidatedBlockLike, ...]: ...


class RunEventPublisherLike(Protocol):
    """runイベント発行境界。"""

    def publish_state(self, run_id: UUID, state: str) -> None: ...

    def publish_message(self, run_id: UUID, text: str) -> None: ...

    def publish_answer(self, run_id: UUID) -> None: ...

    def publish_error(self, run_id: UUID, state: str) -> None: ...


class ClockLike(Protocol):
    """時刻取得境界。"""

    def now_utc(self) -> datetime: ...


class TraceLoggerLike(Protocol):
    """実行時異常のtrace記録境界。"""

    def write_trace(self, stage: str, diagnostic_message: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ExecuteChatRunUseCase:
    """生成、回答検証、採用保存を実行する。"""

    repository: ChatExecutionRepositoryLike
    transaction_manager: TransactionManagerLike
    generation_runner: GenerationRunnerLike
    answer_validator: AnswerValidatorLike
    adopted_artifact_saver: AdoptedArtifactSaverLike
    event_publisher: RunEventPublisherLike
    clock: ClockLike
    trace_logger: TraceLoggerLike
    execution_deadline_seconds: int = _EXECUTION_DEADLINE_SECONDS
    max_regenerations: int = 2

    def execute(self, command: ExecuteChatRunCommand) -> None:
        context = self.repository.load_runtime_context(command.chat_id)
        if context is None:
            return
        deadline_at = self.clock.now_utc() + timedelta(
            seconds=self.execution_deadline_seconds,
        )
        generation_conversation_id = context.generation_conversation_id
        validation_conversation_id = context.validation_conversation_id
        retry_count = 0
        regeneration_instruction: str | None = None
        try:
            self._start_run(command.run_id, deadline_at)
            while True:
                generation_result = self._run_generation(
                    command,
                    context,
                    generation_conversation_id,
                    regeneration_instruction,
                    deadline_at,
                )
                generation_conversation_id = generation_result.conversation_id
                if self._remaining_seconds(deadline_at) <= 0:
                    self._timeout(command.run_id)
                    return
                self._start_validation(command.run_id)
                self._message(command.run_id, "回答候補を検証しています。")
                validation_result = self.answer_validator.execute(
                    ValidateAnswerCommand(
                        chat_id=command.chat_id,
                        run_id=command.run_id,
                        user_id=context.user_id,
                        session_id=context.session_id,
                        candidate_json=generation_result.final_answer_json,
                        artifacts_dir=generation_result.artifacts_dir,
                        retry_count=retry_count,
                        max_regenerations=self.max_regenerations,
                        remaining_seconds=self._remaining_seconds(deadline_at),
                        trace_id=command.trace_id,
                    )
                )
                validation_conversation_id = (
                    validation_result.validation_conversation_id
                    or validation_conversation_id
                )
                self._save_validation_conversation_id(
                    command.chat_id,
                    generation_conversation_id,
                    validation_conversation_id,
                )
                status = _status_name(validation_result.status)
                if (
                    status == ValidationStatus.ACCEPTED.value
                    and validation_result.answer is not None
                ):
                    self._complete(
                        command,
                        context,
                        validation_result.answer,
                        generation_result.artifacts_dir,
                    )
                    return
                if status == ValidationStatus.REGENERATE.value:
                    retry_count += 1
                    regeneration_instruction = (
                        validation_result.regeneration_instruction
                    )
                    self._resume_generation(command.run_id, deadline_at)
                    self._message(command.run_id, "回答を修正します。")
                    continue
                self._validation_failed(command.run_id, validation_result)
                return
        except AppError as error:
            self._handle_app_error(command.run_id, error)
        except Exception as error:
            self._handle_unexpected_error(command.run_id, error)

    def _start_run(self, run_id: UUID, deadline_at: datetime) -> None:
        with self.transaction_manager:
            self.repository.mark_run_running(run_id, deadline_at)
            self.repository.save_intermediate_message(run_id, "作業を開始します。")
        self.event_publisher.publish_state(run_id, RunState.RUNNING.value)
        self.event_publisher.publish_message(run_id, "作業を開始します。")

    def _run_generation(
        self,
        command: ExecuteChatRunCommand,
        context: ChatRuntimeContext,
        generation_conversation_id: str | None,
        regeneration_instruction: str | None,
        deadline_at: datetime,
    ) -> GenerationResultLike:
        result = self.generation_runner.run_generation(
            CodexGenerationRequest(
                chat_id=command.chat_id,
                run_id=command.run_id,
                user_id=context.user_id,
                session_id=context.session_id,
                user_instruction=context.user_instruction,
                resume_conversation_id=generation_conversation_id,
                regeneration_instruction=regeneration_instruction,
                remaining_seconds=self._remaining_seconds(deadline_at),
            )
        )
        for message in result.progress_messages:
            self._message(command.run_id, message)
        self._message(command.run_id, "作業が完了しました。")
        return result

    def _start_validation(self, run_id: UUID) -> None:
        with self.transaction_manager:
            self.repository.mark_run_validating(run_id)
            self.repository.save_intermediate_message(
                run_id,
                "回答の検証を開始します。",
            )
        self.event_publisher.publish_state(run_id, RunState.VALIDATING.value)
        self.event_publisher.publish_message(run_id, "回答の検証を開始します。")

    def _resume_generation(self, run_id: UUID, deadline_at: datetime) -> None:
        with self.transaction_manager:
            self.repository.mark_run_running(run_id, deadline_at)
        self.event_publisher.publish_state(run_id, RunState.RUNNING.value)

    def _save_validation_conversation_id(
        self,
        chat_id: UUID,
        generation_conversation_id: str | None,
        validation_conversation_id: str | None,
    ) -> str | None:
        with self.transaction_manager:
            self.repository.save_conversation_ids(
                chat_id,
                generation_conversation_id,
                validation_conversation_id,
            )
        return validation_conversation_id

    def _complete(
        self,
        command: ExecuteChatRunCommand,
        context: ChatRuntimeContext,
        answer: ValidatedAnswerLike,
        artifacts_dir: Path,
    ) -> None:
        artifact_result = self.adopted_artifact_saver.execute(
            SaveAdoptedArtifactsCommand(
                user_id=context.user_id,
                session_id=context.session_id,
                artifacts_dir=artifacts_dir,
                markdown_blocks=tuple(block.markdown for block in answer.blocks),
            )
        )
        persisted_answer = _answer_data(answer, artifact_result)
        with self.transaction_manager:
            self.repository.save_answers(command.run_id, (persisted_answer,))
            self.repository.mark_run_completed(command.run_id)
            self.repository.save_intermediate_message(
                command.run_id,
                "回答の検証を完了しました。",
            )
        self.event_publisher.publish_message(
            command.run_id,
            "回答の検証を完了しました。",
        )
        self.event_publisher.publish_answer(command.run_id)

    def _validation_failed(
        self,
        run_id: UUID,
        validation_result: ValidationResultLike,
    ) -> None:
        diagnostic = (
            validation_result.diagnostic_message or "回答検証が上限に達しました。"
        )
        with self.transaction_manager:
            self.repository.mark_run_error(run_id, _VALIDATION_ERROR_MESSAGE)
        self.trace_logger.write_trace(
            "answer.validation",
            f"{diagnostic} retry=exhausted",
        )
        self.event_publisher.publish_error(run_id, RunState.ERROR.value)

    def _timeout(self, run_id: UUID) -> None:
        with self.transaction_manager:
            self.repository.mark_run_timed_out(run_id)
        self.trace_logger.write_trace("codex.timeout", "timeout before validation")
        self.event_publisher.publish_error(run_id, RunState.TIMED_OUT.value)

    def _handle_app_error(self, run_id: UUID, error: AppError) -> None:
        diagnostic = error.diagnostic_message
        user_message = (
            _PDF_READ_ERROR_MESSAGE
            if "PDF" in diagnostic
            else _UNEXPECTED_ERROR_MESSAGE
        )
        with self.transaction_manager:
            self.repository.mark_run_error(run_id, user_message)
        stage = "answer.validation" if "PDF" in diagnostic else "codex.generation"
        self.trace_logger.write_trace(stage, diagnostic)
        self.event_publisher.publish_error(run_id, RunState.ERROR.value)

    def _handle_unexpected_error(self, run_id: UUID, error: Exception) -> None:
        with self.transaction_manager:
            self.repository.mark_run_error(run_id, _UNEXPECTED_ERROR_MESSAGE)
        self.trace_logger.write_trace("answer.adoption", str(error))
        self.event_publisher.publish_error(run_id, RunState.ERROR.value)

    def _message(self, run_id: UUID, text: str) -> None:
        with self.transaction_manager:
            self.repository.save_intermediate_message(run_id, text)
        self.event_publisher.publish_message(run_id, text)

    def _remaining_seconds(self, deadline_at: datetime) -> int:
        remaining = int((deadline_at - self.clock.now_utc()).total_seconds())
        return max(remaining, 0)


def _status_name(status: ValidationStatus | str) -> str:
    if isinstance(status, Enum):
        return str(status.value)
    return status


def _answer_data(
    answer: ValidatedAnswerLike,
    artifact_result: SavedArtifactsResultLike,
) -> AnswerData:
    blocks: list[AnswerBlockData] = []
    for position, block in enumerate(answer.blocks, start=1):
        saved_block = artifact_result.blocks[position - 1]
        blocks.append(
            AnswerBlockData(
                answer_block_id=uuid7(),
                position=position,
                markdown=saved_block.markdown,
                references=tuple(
                    DisplayReferenceData(
                        reference_id=uuid7(),
                        position=reference_position,
                        source_type=reference.source_type,
                        label=reference.path,
                        path=reference.path,
                        page_start=reference.page_start,
                        page_end=reference.page_end,
                    )
                    for reference_position, reference in enumerate(
                        block.references,
                        start=1,
                    )
                ),
                artifacts=tuple(
                    ArtifactData(
                        artifact_id=_artifact_uuid(artifact.artifact_id),
                        mime_type=artifact.mime_type,
                        storage_path=artifact.storage_path,
                        created_at=datetime.now().astimezone(),
                    )
                    for artifact in saved_block.artifacts
                ),
            )
        )
    return AnswerData(blocks=tuple(blocks))


def _artifact_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(value)

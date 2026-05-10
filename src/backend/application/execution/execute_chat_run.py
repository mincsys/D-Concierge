from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from backend.application.artifacts.save_adopted_artifacts import (
    SavedAnswerBlocksArtifacts,
)
from backend.application.validation.validate_answer import AnswerValidationResult
from backend.domain.answer.answer_candidate import (
    ParsedAnswerCandidate,
    ParsedReference,
)
from backend.domain.execution.run_state_policy import RunState
from backend.infrastructure.memory.repository import (
    AnswerBlockData,
    AnswerData,
    ArtifactData,
    DisplayReferenceData,
)
from backend.shared.errors import (
    AppError,
    ErrorClass,
    ReferencePdfReadError,
    RunTimeoutError,
)
from backend.shared.tracing import TraceLogger, TraceLogRecord

GENERATION_FAILURE_MESSAGE = (
    "回答生成に失敗しました。ユーザ指示を見直して再度お試しください。"
)
TIMEOUT_FAILURE_MESSAGE = (
    "回答生成が時間内に完了しませんでした。ユーザ指示を絞って再度お試しください。"
)
UNEXPECTED_FAILURE_MESSAGE = "処理中にエラーが発生しました。"
CANCELED_MESSAGE = "処理をキャンセルしました。"
WORK_STARTED_MESSAGE = "作業を開始します。"
WORK_COMPLETED_MESSAGE = "作業が完了しました。"
VALIDATION_STARTED_MESSAGE = "回答の検証を開始します。"
VALIDATION_COMPLETED_MESSAGE = "回答の検証を完了しました。"
ANSWER_REVISION_MESSAGE = "回答を修正します。"


@dataclass(frozen=True, slots=True)
class CodexRunResult:
    """Codex生成結果。"""

    conversation_id: str
    intermediate_messages: tuple[str, ...]
    final_answer_json: str


@dataclass(frozen=True, slots=True)
class RunEvent:
    """run ID単位で発行するSSE向けイベント。"""

    event: Literal["state", "message", "answer", "error", "canceled"]
    chat_id: UUID
    run_id: UUID
    state: RunState | None = None
    text: str | None = None
    answer: AnswerData | None = None
    user_message: str | None = None


class ChatExecutionRepository(Protocol):
    """チャット実行処理が利用するRepository境界。"""

    def get_run_instruction(self, chat_id: UUID, run_id: UUID) -> str:
        """runに対応するユーザ指示本文を返す。"""

    def get_run_state(self, chat_id: UUID, run_id: UUID) -> RunState:
        """runの現在状態を返す。"""

    def set_run_state(
        self,
        chat_id: UUID,
        run_id: UUID,
        state: RunState,
        user_message: str | None = None,
    ) -> None:
        """run状態を更新する。"""

    def update_run_state_if_current(
        self,
        chat_id: UUID,
        run_id: UUID,
        expected_states: tuple[RunState, ...],
        state: RunState,
        user_message: str | None = None,
        execution_deadline_at: datetime | None = None,
    ) -> bool:
        """期待状態に一致する場合だけrun状態を更新する。"""

    def add_intermediate_message(self, chat_id: UUID, run_id: UUID, text: str) -> None:
        """中間メッセージを保存する。"""

    def save_completed_answer(
        self,
        chat_id: UUID,
        run_id: UUID,
        answer: AnswerData,
    ) -> None:
        """検証済み回答を保存する。"""


class CodexGenerationRunner(Protocol):
    """生成用Codex実行境界。"""

    def run_generation(
        self,
        chat_id: UUID,
        run_id: UUID,
        user_instruction: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> CodexRunResult:
        """生成用Codexを実行し、構造化結果を返す。"""


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
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        timeout_seconds: int,
        on_intermediate_message: Callable[[str], None] | None = None,
    ) -> AnswerValidationResult:
        """回答候補を検証し、採用可否を返す。"""


class AdoptedArtifactSaver(Protocol):
    """採用済み回答の成果物保存境界。"""

    def save_for_answer_blocks(
        self,
        markdowns: tuple[str, ...],
        run_id: UUID,
        session_workdir: Path,
        trace_id: str,
    ) -> SavedAnswerBlocksArtifacts:
        """回答本文内の成果物参照を保存済みURLへ置換する。"""


class SessionWorkdirResolver(Protocol):
    """チャット単位の生成用Codex作業領域解決境界。"""

    def resolve_generation_workdir(self, chat_id: UUID) -> Path:
        """生成用Codexのセッション作業領域を返す。"""


class ExecuteChatRunUseCase:
    """受付済みrunの生成、固定検証、回答保存、イベント発行を調停する。"""

    def __init__(
        self,
        repository: ChatExecutionRepository,
        codex_runner: CodexGenerationRunner,
        answer_validator: AnswerValidator,
        event_publisher: RunEventPublisher,
        artifact_saver: AdoptedArtifactSaver | None = None,
        session_workdir: Path | None = None,
        session_workdir_resolver: SessionWorkdirResolver | None = None,
        trace_logger: TraceLogger | None = None,
        timeout_seconds: int = 300,
        clock: Callable[[], datetime] | None = None,
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
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    def execute(self, chat_id: UUID, run_id: UUID, trace_id: str = "") -> None:
        """受付済みrunを実行し、完了またはエラーへ終端する。"""
        execution_deadline_at = self._clock() + timedelta(seconds=self._timeout_seconds)
        self._write_trace(
            TraceLogRecord(
                trace_id=trace_id,
                event_name="execution_started",
                stage="execution",
                chat_id=chat_id,
                run_id=run_id,
                execution_deadline_at=execution_deadline_at,
            )
        )
        try:
            self._execute(chat_id, run_id, trace_id, execution_deadline_at)
        except RunTimeoutError as exc:
            self._finish_timeout(chat_id, run_id)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_timeout",
                    stage="execution",
                    chat_id=chat_id,
                    run_id=run_id,
                    exception_type=type(exc).__name__,
                    run_state="タイムアウト",
                    timeout_state="codex_exec_timeout",
                    message=TIMEOUT_FAILURE_MESSAGE,
                )
            )
        except ReferencePdfReadError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                self._write_trace(
                    TraceLogRecord(
                        trace_id=trace_id,
                        event_name="execution_canceled",
                        stage="execution",
                        chat_id=chat_id,
                        run_id=run_id,
                        run_state="キャンセル済み",
                        cancel_state="canceled",
                    )
                )
                return
            self._finish_error(chat_id, run_id, exc.user_message)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage="validation",
                    chat_id=chat_id,
                    run_id=run_id,
                    error_class=exc.error_class.value,
                    exception_type=type(exc).__name__,
                    run_state="エラー",
                    validation_failure_reason=exc.diagnostic_message,
                    message=exc.user_message,
                )
            )
        except AppError as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                self._write_trace(
                    TraceLogRecord(
                        trace_id=trace_id,
                        event_name="execution_canceled",
                        stage="execution",
                        chat_id=chat_id,
                        run_id=run_id,
                        run_state="キャンセル済み",
                        cancel_state="canceled",
                    )
                )
                return
            self._finish_error(chat_id, run_id, GENERATION_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage="generation",
                    chat_id=chat_id,
                    run_id=run_id,
                    error_class=exc.error_class.value,
                    exception_type=type(exc).__name__,
                    run_state="エラー",
                    message=exc.user_message,
                )
            )
        except Exception as exc:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                self._write_trace(
                    TraceLogRecord(
                        trace_id=trace_id,
                        event_name="execution_canceled",
                        stage="execution",
                        chat_id=chat_id,
                        run_id=run_id,
                        run_state="キャンセル済み",
                        cancel_state="canceled",
                    )
                )
                return
            self._finish_error(chat_id, run_id, UNEXPECTED_FAILURE_MESSAGE)
            self._write_trace(
                TraceLogRecord(
                    trace_id=trace_id,
                    event_name="execution_failed",
                    stage="execution",
                    chat_id=chat_id,
                    run_id=run_id,
                    error_class=ErrorClass.SYSTEM.value,
                    exception_type=type(exc).__name__,
                    run_state="エラー",
                    message=str(exc),
                )
            )

    def _execute(
        self,
        chat_id: UUID,
        run_id: UUID,
        trace_id: str,
        execution_deadline_at: datetime,
    ) -> None:
        user_instruction = self._repository.get_run_instruction(chat_id, run_id)
        if self._is_canceled(chat_id, run_id):
            self._finish_canceled(chat_id, run_id)
            return

        prompt = user_instruction
        retry_count = 0
        while True:
            generation_timeout_seconds = self._remaining_seconds(execution_deadline_at)
            self._change_state(
                chat_id,
                run_id,
                "実行中",
                expected_states=("受付",) if retry_count == 0 else ("検証中",),
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
            validation_timeout_seconds = self._remaining_seconds(execution_deadline_at)
            self._change_state(
                chat_id,
                run_id,
                "検証中",
                expected_states=("実行中",),
            )
            self._record_intermediate_message(
                chat_id, run_id, VALIDATION_STARTED_MESSAGE
            )
            validation = self._answer_validator.validate(
                result.final_answer_json,
                retry_count,
                chat_id,
                run_id,
                trace_id,
                timeout_seconds=validation_timeout_seconds,
                on_intermediate_message=lambda message: (
                    self._record_intermediate_message(chat_id, run_id, message)
                ),
            )
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
                return

            match validation.status:
                case "採用可能":
                    if validation.candidate is None:
                        self._finish_error(
                            chat_id, run_id, "回答を検証できませんでした。"
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
                case "再生成指示":
                    retry_count += 1
                    prompt = (
                        f"{user_instruction}\n\n{validation.regeneration_instruction}"
                    )
                case "失敗":
                    self._finish_error(
                        chat_id,
                        run_id,
                        validation.user_message or "回答を検証できませんでした。",
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
                raise AppError(ErrorClass.CONFLICT, "この処理はキャンセルされました。")
            raise AppError(ErrorClass.CONFLICT, "実行状態が変更されています。")
        self._event_publisher.publish(
            RunEvent(event="state", chat_id=chat_id, run_id=run_id, state=state)
        )

    def _record_intermediate_message(
        self, chat_id: UUID, run_id: UUID, message: str
    ) -> None:
        self._repository.add_intermediate_message(chat_id, run_id, message)
        self._event_publisher.publish(
            RunEvent(
                event="message",
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
        artifacts: tuple[ArtifactData, ...] = ()
        if self._artifact_saver is not None:
            session_workdir = self._resolve_session_workdir(chat_id)
            if session_workdir is None:
                self._finish_error(chat_id, run_id, "回答を検証できませんでした。")
                return
            saved = self._artifact_saver.save_for_answer_blocks(
                markdowns=markdowns,
                run_id=run_id,
                session_workdir=session_workdir,
                trace_id=trace_id,
            )
            markdowns = saved.markdowns
            artifacts = tuple(
                ArtifactData(
                    artifact_id=artifact.artifact_id,
                    mime_type=artifact.mime_type,
                    relative_path=artifact.relative_path,
                )
                for artifact in saved.artifacts
            )

        answer = AnswerData(
            blocks=tuple(
                AnswerBlockData(
                    markdown=markdown,
                    references=tuple(
                        DisplayReferenceData(
                            reference_id=uuid4(),
                            source_type="pdf",
                            label=reference.label,
                            relative_path=reference.relative_path,
                            page_start=reference.page_start,
                            page_end=reference.page_end,
                        )
                        for reference in _merge_references(block.references)
                    ),
                )
                for markdown, block in zip(markdowns, candidate.blocks, strict=True)
            ),
            artifacts=artifacts,
        )
        self._repository.save_completed_answer(chat_id, run_id, answer)
        self._repository.set_run_state(chat_id, run_id, "完了")
        self._event_publisher.publish(
            RunEvent(
                event="answer",
                chat_id=chat_id,
                run_id=run_id,
                state="完了",
                answer=answer,
            )
        )
        self._write_trace(
            TraceLogRecord(
                trace_id=trace_id,
                event_name="execution_finished",
                stage="execution",
                chat_id=chat_id,
                run_id=run_id,
                run_state="完了",
            )
        )

    def _resolve_session_workdir(self, chat_id: UUID) -> Path | None:
        if self._session_workdir_resolver is not None:
            return self._session_workdir_resolver.resolve_generation_workdir(chat_id)
        return self._session_workdir

    def _finish_error(self, chat_id: UUID, run_id: UUID, user_message: str) -> None:
        updated = self._repository.update_run_state_if_current(
            chat_id=chat_id,
            run_id=run_id,
            expected_states=("受付", "実行中", "検証中"),
            state="エラー",
            user_message=user_message,
        )
        if not updated:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
            return
        self._event_publisher.publish(
            RunEvent(
                event="error",
                chat_id=chat_id,
                run_id=run_id,
                state="エラー",
                user_message=user_message,
            )
        )

    def _finish_timeout(self, chat_id: UUID, run_id: UUID) -> None:
        updated = self._repository.update_run_state_if_current(
            chat_id=chat_id,
            run_id=run_id,
            expected_states=("受付", "実行中", "検証中"),
            state="タイムアウト",
            user_message=TIMEOUT_FAILURE_MESSAGE,
        )
        if not updated:
            if self._is_canceled(chat_id, run_id):
                self._finish_canceled(chat_id, run_id)
            return
        self._event_publisher.publish(
            RunEvent(
                event="error",
                chat_id=chat_id,
                run_id=run_id,
                state="タイムアウト",
                user_message=TIMEOUT_FAILURE_MESSAGE,
            )
        )

    def _finish_canceled(self, chat_id: UUID, run_id: UUID) -> None:
        self._repository.update_run_state_if_current(
            chat_id=chat_id,
            run_id=run_id,
            expected_states=("受付", "実行中", "検証中", "キャンセル要求中"),
            state="キャンセル済み",
            user_message=CANCELED_MESSAGE,
        )
        self._event_publisher.publish(
            RunEvent(
                event="canceled",
                chat_id=chat_id,
                run_id=run_id,
                state="キャンセル済み",
                user_message=CANCELED_MESSAGE,
            )
        )

    def _is_canceled(self, chat_id: UUID, run_id: UUID) -> bool:
        return self._repository.get_run_state(chat_id, run_id) in {
            "キャンセル要求中",
            "キャンセル済み",
        }

    def _remaining_seconds(self, execution_deadline_at: datetime) -> int:
        remaining = (execution_deadline_at - self._clock()).total_seconds()
        if remaining <= 0:
            raise RunTimeoutError()
        return max(1, ceil(remaining))

    def _write_trace(self, record: TraceLogRecord) -> None:
        if self._trace_logger is not None:
            self._trace_logger.write(record)


def _merge_references(
    references: tuple[ParsedReference, ...],
) -> tuple[ParsedReference, ...]:
    sorted_references = sorted(
        references,
        key=lambda reference: (
            reference.relative_path,
            reference.page_start,
            reference.page_end,
        ),
    )
    merged: list[ParsedReference] = []
    for reference in sorted_references:
        if not merged:
            merged.append(reference)
            continue

        current = merged[-1]
        if (
            current.relative_path == reference.relative_path
            and reference.page_start <= current.page_end + 1
        ):
            merged[-1] = ParsedReference(
                label=current.label,
                relative_path=current.relative_path,
                page_start=current.page_start,
                page_end=max(current.page_end, reference.page_end),
            )
            continue

        merged.append(reference)
    return tuple(merged)

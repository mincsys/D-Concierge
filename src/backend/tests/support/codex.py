from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol, TypedDict
from uuid import UUID

from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.engine import Engine

from backend.application.ports.codex.dto import (
    CodexGenerationRequest,
    CodexGenerationResult,
    ReferenceValidationResult,
    ValidatorCodexRequest,
    ValidatorCodexResult,
)
from backend.application.ports.database.dto import AnswerData, ChatRuntimeContext
from backend.application.ports.filesystem.dto import AdoptedArtifactSaveResult
from backend.domain.execution.run_state import RunState
from backend.tests.support.chat import (
    CHAT_ID_VALUE,
    F003_USER_ID,
    FIXED_CHAT_NOW,
    SESSION_ID_VALUE,
    TRACE_ID_VALUE,
)

GENERATION_THREAD_ID = "gen-thread-001"
VALIDATION_THREAD_ID = "val-thread-001"
REFERENCE_PATH = "manuals/pump.pdf"
ARTIFACT_SOURCE_PATH = "artifacts/diagram.svg"
SAVED_ARTIFACT_URL = "/api/artifacts/aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa"

type ValidationStatusName = Literal["accepted", "regenerate", "failed"]


class CandidateLocatorPayload(TypedDict):
    path: str
    start_page: int
    end_page: int


class CandidateReferencePayload(TypedDict):
    source_type: str
    locator: CandidateLocatorPayload


class CandidateAnswerPayload(TypedDict):
    text: str
    references: list[CandidateReferencePayload]


class CandidateFinalPayload(TypedDict):
    kind: Literal["final"]
    answers: list[CandidateAnswerPayload]


class CandidateEnvelopePayload(TypedDict):
    payload: CandidateFinalPayload


class ValidatorFinalPayload(TypedDict):
    kind: Literal["final"]
    valid: bool
    comment: str


class ValidatorEnvelopePayload(TypedDict):
    payload: ValidatorFinalPayload


class GenerationRequestLike(Protocol):
    """生成用Codex実行境界へ渡す要求の観測項目。"""

    @property
    def chat_id(self) -> UUID: ...

    @property
    def run_id(self) -> UUID: ...

    @property
    def session_id(self) -> UUID: ...

    @property
    def user_instruction(self) -> str: ...

    @property
    def remaining_seconds(self) -> int: ...

    @property
    def resume_conversation_id(self) -> str | None: ...

    @property
    def regeneration_instruction(self) -> str | None: ...


class ValidationRequestLike(Protocol):
    """検証用Codex実行境界へ渡す要求の観測項目。"""

    @property
    def chat_id(self) -> UUID: ...

    @property
    def run_id(self) -> UUID: ...

    @property
    def session_id(self) -> UUID: ...

    @property
    def candidate_json(self) -> str: ...

    @property
    def remaining_seconds(self) -> int: ...

    @property
    def resume_conversation_id(self) -> str | None: ...

    @property
    def artifacts_readonly_dir(self) -> Path | None: ...


class ArtifactSourceLike(Protocol):
    """採用済み成果物保存へ渡す候補ファイルの観測項目。"""

    @property
    def session_id(self) -> UUID: ...

    @property
    def user_id(self) -> str: ...

    @property
    def relative_path(self) -> str: ...


GenerationRunResultRecord = CodexGenerationResult
ValidatorRunResultRecord = ValidatorCodexResult
ReferenceValidationRecord = ReferenceValidationResult


@dataclass(frozen=True, slots=True)
class SavedArtifactRecord:
    artifact_id: UUID
    storage_path: str
    public_url: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class StateChangeRecord:
    run_id: UUID
    state: str
    user_message: str | None


@dataclass(frozen=True, slots=True)
class IntermediateMessageRecord:
    run_id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class ConversationIdRecord:
    chat_id: UUID
    generation_conversation_id: str | None
    validation_conversation_id: str | None


@dataclass(frozen=True, slots=True)
class PublishedEventRecord:
    run_id: UUID
    event_name: str
    payload_state: str
    text: str | None = None


@dataclass(frozen=True, slots=True)
class TraceRecord:
    stage: str
    diagnostic_message: str


@dataclass(slots=True)
class FakeCodexGenerationRunner:
    results: list[GenerationRunResultRecord]
    requests: list[CodexGenerationRequest] = field(default_factory=list)

    def run_generation(
        self,
        request: CodexGenerationRequest,
    ) -> GenerationRunResultRecord:
        self.requests.append(request)
        if not self.results:
            raise RuntimeError("生成用CodexのFake結果が不足しています。")
        return self.results.pop(0)


@dataclass(slots=True)
class FakeValidatorCodexRunner:
    results: list[ValidatorRunResultRecord]
    requests: list[ValidatorCodexRequest] = field(default_factory=list)

    def run_validation(
        self,
        request: ValidatorCodexRequest,
    ) -> ValidatorRunResultRecord:
        self.requests.append(request)
        if not self.results:
            raise RuntimeError("検証用CodexのFake結果が不足しています。")
        return self.results.pop(0)


@dataclass(slots=True)
class FakeReferenceFileValidator:
    records: dict[str, ReferenceValidationRecord]
    requested_paths: list[str] = field(default_factory=list)

    def validate_pdf_reference(
        self,
        path: str,
        page_start: int,
        page_end: int,
    ) -> ReferenceValidationRecord:
        self.requested_paths.append(path)
        return self.records.get(
            path,
            ReferenceValidationRecord(
                path=path,
                page_start=page_start,
                page_end=page_end,
                exists=False,
                readable=False,
                page_count=0,
            ),
        )


@dataclass(slots=True)
class FakeAdoptedArtifactStore:
    saved: list[ArtifactSourceLike] = field(default_factory=list)
    next_artifact_id: UUID = UUID("aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa")

    def save_adopted_artifact(
        self,
        source: ArtifactSourceLike,
    ) -> AdoptedArtifactSaveResult:
        self.saved.append(source)
        suffix = source.relative_path.rsplit(".", maxsplit=1)[-1]
        return AdoptedArtifactSaveResult(
            artifact_id=str(self.next_artifact_id),
            storage_path=f"{source.user_id}/{source.session_id}/{self.next_artifact_id}.{suffix}",
            public_url=f"/api/artifacts/{self.next_artifact_id}",
            mime_type="image/svg+xml",
        )


@dataclass(slots=True)
class FakeChatExecutionRepository:
    runtime_context: ChatRuntimeContext | None = field(
        default_factory=lambda: ChatRuntimeContext(
            chat_id=CHAT_ID_VALUE,
            user_id=F003_USER_ID,
            session_id=SESSION_ID_VALUE,
            generation_conversation_id=None,
            validation_conversation_id=None,
        ),
    )
    states: list[StateChangeRecord] = field(default_factory=list)
    intermediate_messages: list[IntermediateMessageRecord] = field(default_factory=list)
    conversation_ids: list[ConversationIdRecord] = field(default_factory=list)
    saved_answer_runs: list[UUID] = field(default_factory=list)
    saved_answer_markdown: list[str] = field(default_factory=list)

    def load_runtime_context(self, chat_id: UUID) -> ChatRuntimeContext | None:
        if self.runtime_context is None or self.runtime_context.chat_id != chat_id:
            return None
        return self.runtime_context

    def mark_run_running(
        self,
        run_id: UUID,
        execution_deadline_at: datetime,
    ) -> None:
        self.states.append(
            StateChangeRecord(
                run_id=run_id,
                state=RunState.RUNNING.value,
                user_message=None,
            ),
        )

    def mark_run_validating(self, run_id: UUID) -> None:
        self.states.append(
            StateChangeRecord(
                run_id=run_id,
                state=RunState.VALIDATING.value,
                user_message=None,
            ),
        )

    def mark_run_completed(self, run_id: UUID) -> None:
        self.states.append(
            StateChangeRecord(
                run_id=run_id,
                state=RunState.COMPLETED.value,
                user_message=None,
            ),
        )

    def mark_run_error(self, run_id: UUID, diagnostic_message: str) -> None:
        self.states.append(
            StateChangeRecord(
                run_id=run_id,
                state=RunState.ERROR.value,
                user_message=diagnostic_message,
            ),
        )

    def mark_run_timed_out(self, run_id: UUID) -> None:
        self.states.append(
            StateChangeRecord(
                run_id=run_id,
                state=RunState.TIMED_OUT.value,
                user_message="処理がタイムアウトしました。",
            ),
        )

    def save_intermediate_message(self, run_id: UUID, text: str) -> None:
        self.intermediate_messages.append(
            IntermediateMessageRecord(run_id=run_id, text=text),
        )

    def save_conversation_ids(
        self,
        chat_id: UUID,
        generation_conversation_id: str | None,
        validation_conversation_id: str | None,
    ) -> None:
        self.conversation_ids.append(
            ConversationIdRecord(
                chat_id=chat_id,
                generation_conversation_id=generation_conversation_id,
                validation_conversation_id=validation_conversation_id,
            ),
        )

    def save_answers(self, run_id: UUID, answers: tuple[AnswerData, ...]) -> None:
        self.saved_answer_runs.append(run_id)
        for answer in answers:
            self.saved_answer_markdown.extend(block.markdown for block in answer.blocks)


@dataclass(slots=True)
class FakeRunEventPublisher:
    events: list[PublishedEventRecord] = field(default_factory=list)

    def publish_state(self, run_id: UUID, state: str) -> None:
        self.events.append(
            PublishedEventRecord(
                run_id=run_id,
                event_name="state",
                payload_state=state,
            ),
        )

    def publish_message(self, run_id: UUID, text: str) -> None:
        self.events.append(
            PublishedEventRecord(
                run_id=run_id,
                event_name="message",
                payload_state="",
                text=text,
            ),
        )

    def publish_answer(self, run_id: UUID) -> None:
        self.events.append(
            PublishedEventRecord(
                run_id=run_id,
                event_name="answer",
                payload_state=RunState.COMPLETED.value,
            ),
        )

    def publish_error(self, run_id: UUID, state: str) -> None:
        self.events.append(
            PublishedEventRecord(
                run_id=run_id,
                event_name="error",
                payload_state=state,
            ),
        )


@dataclass(slots=True)
class FakeTraceLogger:
    records: list[TraceRecord] = field(default_factory=list)

    def write_trace(self, stage: str, diagnostic_message: str) -> None:
        self.records.append(
            TraceRecord(stage=stage, diagnostic_message=diagnostic_message),
        )


def valid_candidate_json(markdown: str | None = None) -> str:
    text = markdown or (
        "ポンプは定期点検が必要です。"
        f" 詳細は[図]({ARTIFACT_SOURCE_PATH})を確認してください。"
    )
    payload: CandidateEnvelopePayload = {
        "payload": {
            "kind": "final",
            "answers": [
                {
                    "text": text,
                    "references": [
                        {
                            "source_type": "pdf",
                            "locator": {
                                "path": f"data_source/{REFERENCE_PATH}",
                                "start_page": 2,
                                "end_page": 3,
                            },
                        },
                    ],
                },
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def invalid_reference_candidate_json() -> str:
    payload: CandidateEnvelopePayload = {
        "payload": {
            "kind": "final",
            "answers": [
                {
                    "text": "参照元が不正です。",
                    "references": [
                        {
                            "source_type": "pdf",
                            "locator": {
                                "path": "../secret.pdf",
                                "start_page": 4,
                                "end_page": 2,
                            },
                        },
                    ],
                },
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def empty_answers_candidate_json() -> str:
    return '{"payload":{"kind":"final","answers":[]}}'


def non_pdf_reference_candidate_json() -> str:
    return (
        '{"payload":{"kind":"final","answers":[{"text":"本文",'
        '"references":[{"source_type":"web","locator":{'
        '"path":"data_source/manuals/pump.pdf",'
        '"start_page":1,"end_page":1}}]}]}}'
    )


def dangerous_html_candidate_json() -> str:
    return valid_candidate_json('<img src="x" onerror="alert(1)">')


def artifact_link_candidate_json(markdown_link: str) -> str:
    return valid_candidate_json(f"成果物を確認してください。{markdown_link}")


def validator_result_json(valid: bool, comment: str = "") -> str:
    payload: ValidatorEnvelopePayload = {
        "payload": {
            "kind": "final",
            "valid": valid,
            "comment": comment,
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def generation_result(
    tmp_path: Path,
    candidate_json: str | None = None,
) -> GenerationRunResultRecord:
    artifacts_dir = (
        tmp_path
        / "codex"
        / "sessions"
        / F003_USER_ID
        / str(SESSION_ID_VALUE)
        / "artifacts"
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "diagram.svg").write_text("<svg />", encoding="utf-8")
    return GenerationRunResultRecord(
        conversation_id=GENERATION_THREAD_ID,
        progress_messages=("調査しています。",),
        final_answer_json=candidate_json or valid_candidate_json(),
        artifacts_dir=artifacts_dir,
    )


def validation_result(
    valid: bool = True,
    comment: str = "",
) -> ValidatorRunResultRecord:
    return ValidatorRunResultRecord(
        conversation_id=VALIDATION_THREAD_ID,
        progress_messages=("回答候補を検証しています。",),
        final_result_json=validator_result_json(valid=valid, comment=comment),
    )


def reference_validation_records() -> dict[str, ReferenceValidationRecord]:
    return {
        REFERENCE_PATH: ReferenceValidationRecord(
            path=REFERENCE_PATH,
            page_start=2,
            page_end=3,
            exists=True,
            readable=True,
            page_count=8,
        ),
    }


def deadline_after_start(minutes: int = 10) -> datetime:
    return FIXED_CHAT_NOW + timedelta(minutes=minutes)


def metadata_table(engine: Engine, table_name: str) -> Table:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=(table_name,))
    return metadata.tables[table_name]


def saved_answer_count(database_url: str, run_id: UUID) -> int:
    engine = create_engine(database_url)
    try:
        answer_blocks = metadata_table(engine, "answer_blocks")
        with engine.connect() as connection:
            value = connection.scalar(
                select(func.count())
                .select_from(answer_blocks)
                .where(answer_blocks.c.run_id == run_id),
            )
    finally:
        engine.dispose()
    assert isinstance(value, int)
    return value


def saved_artifact_paths(database_url: str) -> tuple[str, ...]:
    engine = create_engine(database_url)
    try:
        artifacts = metadata_table(engine, "artifacts")
        with engine.connect() as connection:
            rows = connection.execute(
                select(artifacts.c.storage_path).order_by(artifacts.c.storage_path),
            )
    finally:
        engine.dispose()
    return tuple(str(row[0]) for row in rows)


def fixed_trace_id() -> str:
    return TRACE_ID_VALUE

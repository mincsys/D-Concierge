from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pypdf import PdfWriter

from backend.application.ports.codex.dto import (
    ReferenceValidationResult,
    ValidatorCodexRunResult,
)
from backend.application.ports.database.interface import (
    ChatRuntimeRepositoryPort,
    TransactionManagerPort,
)
from backend.domain.answer.answer_candidate import (
    InvalidReferencePageRangeFailure,
    InvalidReferencePathFailure,
    ParsedAnswerBlock,
    ParsedAnswerCandidate,
)
from backend.domain.references.pdf_reference import PdfLocator, PdfReference
from backend.infrastructure.codex.codex_event_kind import CodexEventKind
from backend.infrastructure.codex.codex_runner import (
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.jsonl_event_parser import (
    ParsedCodexEvent,
)
from backend.infrastructure.codex.reference_validator import (
    CodexReferenceFileValidator,
    CodexValidationRunnerAdapter,
    InfrastructureCodexRunner,
)
from backend.infrastructure.config.models import ValidatorConfig
from backend.shared.errors.errors import (
    ReferencePdfReadError,
    ValidationWorkspacePreparationError,
)
from backend.tests.support.memory_repository import InMemoryChatRepository
from backend.tests.support.symlink import require_symlink_support
from backend.tests.support.transaction_manager import NoopTransactionManager


def test_codex_validation_runner_runs_validation_and_saves_resume_id(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。確認：promptをそのまま渡し、resume idを保存する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    repository.save_validation_conversation_id(accepted.chat_id, "previous-val-thread")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind=CodexEventKind.THREAD_STARTED,
                    event_type="thread.started",
                    thread_id="next-val-thread",
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.TURN_COMPLETED, event_type="turn.completed"
                ),
            ),
            final_message='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
            codex_conversation_id="next-val-thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    runner = _validation_runner(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    result = runner.run_validation(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        prompt='{"input":"value"}',
        timeout_seconds=55,
        trace_id="trace-601",
    )
    saved_context = repository.get_chat_runtime_context(accepted.chat_id)

    assert result == ValidatorCodexRunResult(
        conversation_id="next-val-thread",
        intermediate_messages=(),
        final_output_json='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
    )
    assert saved_context.validation_conversation_id == "next-val-thread"
    assert codex_runner.requests[0].run_id == accepted.run_id
    assert codex_runner.requests[0].prompt == '{"input":"value"}'
    assert codex_runner.requests[0].codex_conversation_id == "previous-val-thread"
    assert codex_runner.requests[0].workdir == (
        tmp_path
        / "codex/sessions_validator"
        / saved_context.user_id
        / str(saved_context.session_id)
    )
    assert codex_runner.requests[0].timeout_seconds == 55
    assert codex_runner.requests[0].trace_id == "trace-601"


def test_codex_validation_runner_prepares_readonly_validation_context(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。確認：検証用readonlyへ共有データソースを提示して起動する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    codex_runner = RecordingCodexRunner(_valid_infrastructure_result())
    runner = _validation_runner(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    runner.run_validation(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        prompt="prompt",
        timeout_seconds=120,
        trace_id="trace",
    )

    readonly_dir = codex_runner.requests[0].workdir / "readonly"
    assert readonly_dir.is_symlink()
    assert readonly_dir.resolve() == datasource_dir.resolve()
    assert (readonly_dir / "manual.pdf").resolve() == datasource_dir / "manual.pdf"
    assert (codex_runner.requests[0].workdir / "tmp").is_dir()


def test_codex_validation_runner_links_generation_artifacts_when_needed(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。確認：成果物リンクがある回答では生成成果物を検証用workdirへ提示する。"""
    require_symlink_support(tmp_path, target_is_directory=True)
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    context = repository.get_chat_runtime_context(accepted.chat_id)
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    generation_workdir = (
        tmp_path / "codex/sessions" / context.user_id / str(context.session_id)
    )
    generation_artifacts = generation_workdir / "artifacts"
    generation_artifacts.mkdir(parents=True)
    (generation_artifacts / "chart.svg").write_text("<svg />", encoding="utf-8")
    codex_runner = RecordingCodexRunner(_valid_infrastructure_result())
    runner = _validation_runner(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    runner.run_validation(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        prompt="prompt",
        timeout_seconds=120,
        trace_id="trace",
        session_workdir=generation_workdir,
        has_artifact_links=True,
    )

    validation_artifacts = codex_runner.requests[0].workdir / "artifacts"
    assert validation_artifacts.is_symlink()
    assert (validation_artifacts / "chart.svg").read_text(encoding="utf-8") == "<svg />"


def test_codex_validation_runner_streams_intermediate_messages(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携の中間メッセージ。確認：検証用agent_message.textを即時通知する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    codex_runner = StreamingRecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind=CodexEventKind.THREAD_STARTED,
                    event_type="thread.started",
                    thread_id="validator-thread",
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"progress","text":"参照元PDFを確認しています。"}}',
                ),
                ParsedCodexEvent(
                    kind=CodexEventKind.AGENT_MESSAGE,
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
                ),
            ),
            final_message='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
            codex_conversation_id="validator-thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    runner = _validation_runner(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )
    streamed_messages: list[str] = []

    result = runner.run_validation(
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        prompt="prompt",
        timeout_seconds=120,
        trace_id="trace",
        on_intermediate_message=streamed_messages.append,
    )

    assert result.intermediate_messages == ()
    assert streamed_messages == ["参照元PDFを確認しています。"]


def test_reference_file_validator_rejects_missing_pdf_before_codex(
    tmp_path: Path,
) -> None:
    """観点：参照元PDF固定検証。確認：存在しないPDFは不合格にする。"""
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    validator = CodexReferenceFileValidator(datasource_dir=datasource_dir)

    result = validator.validate_reference_files(_candidate_with_pdf())

    assert result == ReferenceValidationResult(
        valid=False,
        failure=InvalidReferencePathFailure(("readonly/manual.pdf",)),
    )


def test_reference_file_validator_rejects_page_out_of_range(
    tmp_path: Path,
) -> None:
    """観点：参照元PDF固定検証。確認：PDFに存在しないページ範囲は不合格にする。"""
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=1)
    validator = CodexReferenceFileValidator(datasource_dir=datasource_dir)

    result = validator.validate_reference_files(_candidate_with_pdf())

    assert result.valid is False
    assert isinstance(result.failure, InvalidReferencePageRangeFailure)
    assert [
        (item.path, item.page_start, item.page_end)
        for item in result.failure.page_ranges
    ] == [("readonly/manual.pdf", 1, 2)]


def test_reference_file_validator_raises_when_existing_pdf_is_unreadable(
    tmp_path: Path,
) -> None:
    """観点：参照元PDF固定検証。確認：存在するPDFを読めない場合はシステムエラーにする。"""
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    (datasource_dir / "manual.pdf").write_text("not a pdf", encoding="utf-8")
    validator = CodexReferenceFileValidator(datasource_dir=datasource_dir)

    with pytest.raises(ReferencePdfReadError) as exc_info:
        validator.validate_reference_files(_candidate_with_pdf())

    assert exc_info.value.relative_path == "manual.pdf"
    assert "manual.pdf" in exc_info.value.diagnostic_message


def test_codex_validation_runner_requires_generation_artifacts_when_needed(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。確認：成果物提示が必要なのに生成workdirがない場合は準備エラーにする。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    codex_runner = RecordingCodexRunner(_valid_infrastructure_result())
    runner = _validation_runner(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    with pytest.raises(ValidationWorkspacePreparationError):
        runner.run_validation(
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
            prompt="prompt",
            timeout_seconds=120,
            trace_id="trace",
            has_artifact_links=True,
        )

    assert codex_runner.requests == []


@dataclass(slots=True)
class RecordingCodexRunner:
    result: InfrastructureCodexRunResult
    requests: list[CodexRunRequest] = field(default_factory=list)

    def run_validation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        self.requests.append(request)
        return self.result


@dataclass(slots=True)
class StreamingRecordingCodexRunner(RecordingCodexRunner):
    def run_validation(self, request: CodexRunRequest) -> InfrastructureCodexRunResult:
        self.requests.append(request)
        for event in self.result.events:
            if request.on_event is not None:
                request.on_event(event)
        return self.result


def _candidate_with_pdf() -> ParsedAnswerCandidate:
    return ParsedAnswerCandidate(
        blocks=(
            ParsedAnswerBlock(
                markdown="回答",
                references=(
                    PdfReference(
                        label="manual.pdf",
                        locator=PdfLocator(
                            relative_path="manual.pdf",
                            page_start=1,
                            page_end=2,
                        ),
                    ),
                ),
            ),
        ),
    )


def _validation_runner(
    *,
    repository: ChatRuntimeRepositoryPort,
    codex_runner: InfrastructureCodexRunner,
    datasource_dir: Path,
    tmp_path: Path,
    transaction_manager: TransactionManagerPort | None = None,
) -> CodexValidationRunnerAdapter:
    return CodexValidationRunnerAdapter(
        repository=repository,
        codex_runner=codex_runner,
        validator_config=ValidatorConfig(
            max_retries=3,
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
        ),
        datasource_dir=datasource_dir,
        timeout_seconds=120,
        transaction_manager=transaction_manager or NoopTransactionManager(),
    )


def _valid_infrastructure_result() -> InfrastructureCodexRunResult:
    return InfrastructureCodexRunResult(
        events=(),
        final_message='{"payload":{"kind":"final","valid":true,"comment":""}}',
        codex_conversation_id="thread",
    )


def _write_pdf(path: Path, *, page_count: int) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)

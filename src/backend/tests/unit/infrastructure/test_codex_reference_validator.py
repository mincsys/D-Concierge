import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pypdf import PdfWriter

from backend.application.ports.codex.dto import ReferenceValidationResult
from backend.domain.answer.answer_candidate import (
    ParsedAnswerBlock,
    ParsedAnswerCandidate,
    ParsedReference,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunRequest,
)
from backend.infrastructure.codex.codex_runner import (
    CodexRunResult as InfrastructureCodexRunResult,
)
from backend.infrastructure.codex.jsonl_event_parser import ParsedCodexEvent
from backend.infrastructure.codex.reference_validator import CodexReferenceValidator
from backend.infrastructure.config.models import CodexConfig
from backend.shared.errors import (
    AppError,
    ErrorClass,
    ReferencePdfReadError,
    ValidationResultFormatError,
)
from backend.tests.support.memory_repository import InMemoryChatRepository


def test_codex_reference_validator_runs_validation_and_saves_resume_id(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。確認：検証結果JSONを参照元検証結果へ変換する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    repository.save_validation_conversation_id(accepted.chat_id, "previous-val-thread")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind="thread_started",
                    event_type="thread.started",
                    thread_id="next-val-thread",
                ),
                ParsedCodexEvent(
                    kind="agent_message",
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
                ),
                ParsedCodexEvent(kind="turn_completed", event_type="turn.completed"),
            ),
            final_message='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
            codex_conversation_id="next-val-thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    validator = CodexReferenceValidator(
        repository=repository,
        codex_runner=codex_runner,
        validator_config=CodexConfig(
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
            saved_artifacts_dir=tmp_path / "unused",
        ),
        datasource_dir=datasource_dir,
        timeout_seconds=120,
    )
    candidate = _candidate_with_pdf()

    result = validator.validate_references(
        candidate,
        user_instruction="資料を要約",
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        trace_id="trace-601",
        timeout_seconds=55,
    )
    saved_context = repository.get_chat_runtime_context(accepted.chat_id)

    assert result == ReferenceValidationResult(
        valid=False,
        comment="根拠が不足しています。",
    )
    assert saved_context.validation_conversation_id == "next-val-thread"
    assert codex_runner.requests[0].run_id == accepted.run_id
    assert codex_runner.requests[0].codex_conversation_id == "previous-val-thread"
    assert codex_runner.requests[0].workdir == (
        tmp_path
        / "codex/sessions_validator"
        / str(saved_context.local_user_id)
        / str(saved_context.session_id)
    )
    assert json.loads(codex_runner.requests[0].prompt) == {
        "instruction": "資料を要約",
        "answers": [
            {
                "text": "回答",
                "references": [
                    {
                        "label": "manual.pdf",
                        "path": "readonly/manual.pdf",
                        "page_start": 1,
                        "page_end": 2,
                    }
                ],
            }
        ],
    }
    assert "relative_path" not in codex_runner.requests[0].prompt
    assert "readonly_path" not in codex_runner.requests[0].prompt
    assert codex_runner.requests[0].timeout_seconds == 55
    assert codex_runner.requests[0].trace_id == "trace-601"


def test_codex_reference_validator_prepares_readonly_validation_context(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。

    確認：検証用readonlyへ共有データソースを提示し、回答候補はプロンプトで渡してから起動する。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(),
            final_message='{"payload":{"kind":"final","valid":true,"comment":""}}',
            codex_conversation_id="thread",
        )
    )
    validator = CodexReferenceValidator(
        repository=repository,
        codex_runner=codex_runner,
        validator_config=CodexConfig(
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
            saved_artifacts_dir=tmp_path / "unused",
        ),
        datasource_dir=datasource_dir,
        timeout_seconds=120,
    )
    candidate = _candidate_with_pdf()

    validator.validate_references(
        candidate,
        user_instruction="資料を要約",
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
    )

    readonly_dir = codex_runner.requests[0].workdir / "readonly"
    assert (readonly_dir / "manual.pdf").resolve() == datasource_dir / "manual.pdf"
    assert not (readonly_dir / "answer-candidate.json").exists()
    assert "readonly/manual.pdf" in codex_runner.requests[0].prompt
    assert (codex_runner.requests[0].workdir / "tmp").is_dir()


def test_codex_reference_validator_links_generation_artifacts_when_needed(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。確認：成果物リンクがある回答では生成成果物を検証用workdirへ提示する。"""
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    context = repository.get_chat_runtime_context(accepted.chat_id)
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    generation_workdir = (
        tmp_path
        / "codex/sessions"
        / str(context.local_user_id)
        / str(context.session_id)
    )
    generation_artifacts = generation_workdir / "artifacts"
    generation_artifacts.mkdir(parents=True)
    (generation_artifacts / "chart.svg").write_text("<svg />", encoding="utf-8")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(),
            final_message='{"payload":{"kind":"final","valid":true,"comment":""}}',
            codex_conversation_id="thread",
        )
    )
    validator = _reference_validator(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    validator.validate_references(
        _candidate_with_pdf(),
        user_instruction="資料を要約",
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        session_workdir=generation_workdir,
        has_artifact_links=True,
    )

    validation_artifacts = codex_runner.requests[0].workdir / "artifacts"
    assert validation_artifacts.is_symlink()
    assert (validation_artifacts / "chart.svg").read_text(encoding="utf-8") == "<svg />"


def test_codex_reference_validator_streams_intermediate_messages(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携の中間メッセージ。

    確認：検証用agent_message.textを即時通知し、最終検証結果JSONは通知しない。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    codex_runner = StreamingRecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind="thread_started",
                    event_type="thread.started",
                    thread_id="validator-thread",
                ),
                ParsedCodexEvent(
                    kind="agent_message",
                    event_type="item.completed",
                    text='{"payload":{"kind":"progress","text":"参照元PDFを確認しています。"}}',
                ),
                ParsedCodexEvent(kind="unknown", event_type="item.completed"),
                ParsedCodexEvent(
                    kind="agent_message",
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
                ),
                ParsedCodexEvent(kind="turn_completed", event_type="turn.completed"),
            ),
            final_message='{"payload":{"kind":"final","valid":false,"comment":"根拠が不足しています。"}}',
            codex_conversation_id="validator-thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    validator = CodexReferenceValidator(
        repository=repository,
        codex_runner=codex_runner,
        validator_config=CodexConfig(
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
            saved_artifacts_dir=tmp_path / "unused",
        ),
        datasource_dir=datasource_dir,
        timeout_seconds=120,
    )
    candidate = _candidate_with_pdf()
    streamed_messages: list[str] = []

    result = validator.validate_references(
        candidate,
        user_instruction="資料を要約",
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        on_intermediate_message=streamed_messages.append,
    )

    assert result == ReferenceValidationResult(
        valid=False,
        comment="根拠が不足しています。",
    )
    assert streamed_messages == ["参照元PDFを確認しています。"]


def test_codex_reference_validator_streams_progress_only(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携の中間メッセージ。

    確認：payload.kind=progressだけを通知し、payload.kind=finalは通知しない。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    codex_runner = StreamingRecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(
                ParsedCodexEvent(
                    kind="thread_started",
                    event_type="thread.started",
                    thread_id="validator-thread",
                ),
                ParsedCodexEvent(
                    kind="agent_message",
                    event_type="item.completed",
                    text='{"payload":{"kind":"progress","text":"参照元を確認しています。"}}',
                ),
                ParsedCodexEvent(
                    kind="agent_message",
                    event_type="item.completed",
                    text='{"payload":{"kind":"final","valid":true,"comment":"検証しました。"}}',
                ),
                ParsedCodexEvent(
                    kind="turn_completed",
                    event_type="turn.completed",
                ),
            ),
            final_message='{"payload":{"kind":"final","valid":true,"comment":"検証しました。"}}',
            codex_conversation_id="validator-thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=2)
    validator = CodexReferenceValidator(
        repository=repository,
        codex_runner=codex_runner,
        validator_config=CodexConfig(
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
            saved_artifacts_dir=tmp_path / "unused",
        ),
        datasource_dir=datasource_dir,
        timeout_seconds=120,
    )
    candidate = _candidate_with_pdf()
    streamed_messages: list[str] = []

    result = validator.validate_references(
        candidate,
        user_instruction="資料を要約",
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
        on_intermediate_message=streamed_messages.append,
    )

    assert result == ReferenceValidationResult(
        valid=True,
        comment="検証しました。",
    )
    assert streamed_messages == ["参照元を確認しています。"]


def test_codex_reference_validator_rejects_invalid_context_or_payload(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。

    確認：実行文脈なしは汎用システムエラー、検証結果不正は専用エラーにする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    candidate = _candidate_without_references()
    validator = CodexReferenceValidator(
        repository=repository,
        codex_runner=RecordingCodexRunner(
            result=InfrastructureCodexRunResult(
                events=(),
                final_message='{"payload":{"kind":"final","valid":"yes","comment":""}}',
                codex_conversation_id="thread",
            )
        ),
        validator_config=CodexConfig(
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
            saved_artifacts_dir=tmp_path / "unused",
        ),
        datasource_dir=tmp_path / "readonly",
        timeout_seconds=120,
    )

    with pytest.raises(AppError) as context_error:
        validator.validate_references(candidate, user_instruction="資料を要約")
    with pytest.raises(ValidationResultFormatError) as payload_error:
        validator.validate_references(
            candidate,
            user_instruction="資料を要約",
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
            trace_id="trace-602",
        )

    assert context_error.value.error_class is ErrorClass.SYSTEM
    assert payload_error.value.error_class is ErrorClass.SYSTEM
    assert payload_error.value.diagnostic_message == "検証結果の形式が不正です。"


@pytest.mark.parametrize(
    "final_message",
    (
        '{"payload":{"kind":"progress","text":"検証しています。"}}',
        '{"payload":{"kind":"final","valid":true}}',
        "not-json",
    ),
)
def test_codex_reference_validator_rejects_invalid_final_validation_result(
    tmp_path: Path,
    final_message: str,
) -> None:
    """観点：検証用Codex連携。

    確認：最終検証結果として採用できないJSONは専用エラーにする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    validator = CodexReferenceValidator(
        repository=repository,
        codex_runner=RecordingCodexRunner(
            result=InfrastructureCodexRunResult(
                events=(),
                final_message=final_message,
                codex_conversation_id="thread",
            )
        ),
        validator_config=CodexConfig(
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
            saved_artifacts_dir=tmp_path / "unused",
        ),
        datasource_dir=tmp_path / "readonly",
        timeout_seconds=120,
    )

    with pytest.raises(ValidationResultFormatError):
        validator.validate_references(
            _candidate_without_references(),
            user_instruction="資料を要約",
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
            trace_id="trace-603",
        )


def test_codex_reference_validator_rejects_missing_pdf_before_codex(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。

    確認：参照元PDFが存在しない場合は検証用Codexを起動せず不合格にする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(),
            final_message='{"payload":{"kind":"final","valid":true,"comment":""}}',
            codex_conversation_id="thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    validator = _reference_validator(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    result = validator.validate_references(
        _candidate_with_pdf(),
        user_instruction="資料を要約",
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
    )

    assert result.valid is False
    assert result.comment == (
        "参照元のパスが不正なため、この回答は採用できません。\n"
        "以下のパス指定が間違っています。\n"
        "- readonly/manual.pdf\n"
        "参照元の locator.path は、必ず既存の実PDFファイルへのパスを指す "
        "`readonly/... .pdf` 形式にしてください。\n"
        "回答本文は前回同様にユーザ質問へ完全に回答し、"
        "参照元だけを正しいPDFパスへ修正して最終JSONを再出力してください。"
    )
    assert codex_runner.requests == []


def test_codex_reference_validator_rejects_page_out_of_range_before_codex(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。

    確認：参照元PDFに存在しないページ範囲は検証用Codexを起動せず不合格にする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(),
            final_message='{"payload":{"kind":"final","valid":true,"comment":""}}',
            codex_conversation_id="thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    _write_pdf(datasource_dir / "manual.pdf", page_count=1)
    validator = _reference_validator(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    result = validator.validate_references(
        _candidate_with_pdf(),
        user_instruction="資料を要約",
        chat_id=accepted.chat_id,
        run_id=accepted.run_id,
    )

    assert result.valid is False
    assert result.comment == (
        "参照元のページ範囲が不正なため、この回答は採用できません。\n"
        "以下のページ範囲指定が間違っています。\n"
        "- readonly/manual.pdf 1-2ページ\n"
        "参照元の locator.start_page / locator.end_page は、"
        "指定したPDFに実在するページ範囲を指定してください。\n"
        "回答本文は前回同様にユーザ質問へ完全に回答し、"
        "参照元だけを正しいPDFパスとページ範囲へ修正して"
        "最終JSONを再出力してください。"
    )
    assert codex_runner.requests == []


def test_codex_reference_validator_raises_when_existing_pdf_is_unreadable(
    tmp_path: Path,
) -> None:
    """観点：検証用Codex連携。

    確認：存在するPDFを読み取れない場合は検証用Codexや再生成へ進めず、システムエラーにする。
    """
    repository = InMemoryChatRepository()
    accepted = repository.create_chat_with_first_run("資料を要約")
    codex_runner = RecordingCodexRunner(
        result=InfrastructureCodexRunResult(
            events=(),
            final_message='{"payload":{"kind":"final","valid":true,"comment":""}}',
            codex_conversation_id="thread",
        )
    )
    datasource_dir = tmp_path / "readonly"
    datasource_dir.mkdir()
    (datasource_dir / "manual.pdf").write_text("not a pdf", encoding="utf-8")
    validator = _reference_validator(
        repository=repository,
        codex_runner=codex_runner,
        datasource_dir=datasource_dir,
        tmp_path=tmp_path,
    )

    with pytest.raises(ReferencePdfReadError) as exc_info:
        validator.validate_references(
            _candidate_with_pdf(),
            user_instruction="資料を要約",
            chat_id=accepted.chat_id,
            run_id=accepted.run_id,
        )

    assert exc_info.value.relative_path == "manual.pdf"
    assert "manual.pdf" in exc_info.value.diagnostic_message
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
                    ParsedReference(
                        label="manual.pdf",
                        relative_path="manual.pdf",
                        page_start=1,
                        page_end=2,
                    ),
                ),
            ),
        ),
    )


def _candidate_without_references() -> ParsedAnswerCandidate:
    return ParsedAnswerCandidate(
        blocks=(ParsedAnswerBlock(markdown="回答", references=()),)
    )


def _reference_validator(
    *,
    repository: InMemoryChatRepository,
    codex_runner: RecordingCodexRunner,
    datasource_dir: Path,
    tmp_path: Path,
) -> CodexReferenceValidator:
    return CodexReferenceValidator(
        repository=repository,
        codex_runner=codex_runner,
        validator_config=CodexConfig(
            home=tmp_path / "codex/.codex_validator",
            workdir=tmp_path / "codex/sessions_validator",
            output_schema=tmp_path / "validator-schema.json",
            saved_artifacts_dir=tmp_path / "unused",
        ),
        datasource_dir=datasource_dir,
        timeout_seconds=120,
    )


def _write_pdf(path: Path, *, page_count: int) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)

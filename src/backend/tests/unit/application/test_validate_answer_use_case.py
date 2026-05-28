import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid7

import pytest

from backend.application.ports.codex.dto import (
    ReferenceValidationResult,
    ValidatorCodexRunResult,
)
from backend.application.validation.validate_answer import ValidateAnswerUseCase
from backend.application.validation.validation_status import ValidationStatus
from backend.domain.answer.answer_candidate import (
    InvalidReferencePathFailure,
    ParsedAnswerCandidate,
)
from backend.shared.errors.errors import ValidationResultFormatError


def test_validate_answer_accepts_fixed_and_reference_valid_candidate() -> None:
    """観点：回答検証UseCase。確認：固定検証と参照元検証に合格した回答候補を採用可能として返す。"""
    file_validator = RecordingReferenceFileValidator()
    validator_runner = RecordingValidatorCodexRunner(
        outputs=('{"payload":{"kind":"final","valid":true,"comment":""}}',),
    )
    use_case = _use_case(file_validator, validator_runner)

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=0,
        user_instruction="資料を要約",
        chat_id=uuid7(),
        run_id=uuid7(),
    )

    assert result.status is ValidationStatus.ACCEPTED
    assert result.candidate is not None
    assert result.candidate.blocks[0].markdown == "要点はAです。"
    assert (
        file_validator.validated_candidates[0].blocks[0].references[0].page_start == 2
    )
    prompt = json.loads(validator_runner.prompts[0])
    assert prompt["instruction"] == "資料を要約"
    assert prompt["answers"][0]["text"] == "要点はAです。"


def test_validate_answer_forwards_reference_intermediate_callback() -> None:
    """観点：回答検証UseCaseの検証中間メッセージ。確認：検証用Codexの中間メッセージ通知先を渡す。"""
    messages: list[str] = []
    validator_runner = RecordingValidatorCodexRunner(
        outputs=('{"payload":{"kind":"final","valid":true,"comment":""}}',),
        emitted_message="参照元を確認しています。",
    )
    use_case = _use_case(RecordingReferenceFileValidator(), validator_runner)

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=0,
        user_instruction="資料を要約",
        chat_id=uuid7(),
        run_id=uuid7(),
        on_intermediate_message=messages.append,
    )

    assert result.status is ValidationStatus.ACCEPTED
    assert messages == ["参照元を確認しています。"]


def test_validate_answer_returns_regeneration_for_fixed_validation_failure() -> None:
    """観点：回答検証UseCaseの固定検証失敗。確認：固定検証失敗時は検証用Codexを呼ばない。"""
    file_validator = RecordingReferenceFileValidator()
    validator_runner = RecordingValidatorCodexRunner(
        outputs=('{"payload":{"kind":"final","valid":true,"comment":""}}',),
    )
    use_case = _use_case(file_validator, validator_runner)

    result = use_case.validate(
        '{"payload":{"kind":"final","answers":[{"text":" ","references":[]}]}}',
        retry_count=0,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.regeneration_instruction == (
        "回答JSONの固定検証で不合格になったため、この回答は採用できません。\n"
        "不合格理由：回答本文が空です。payload.answers[0].text が存在しない、"
        "文字列ではない、または空文字列になっています。\n\n"
        "ユーザ指示には完全に回答し、指定スキーマに従って回答を再出力してください。"
    )
    assert file_validator.validated_candidates == []
    assert validator_runner.prompts == []


def test_validate_answer_returns_specific_regeneration_for_invalid_paths() -> None:
    """観点：回答検証UseCaseの固定検証失敗。確認：参照元path不正時は具体的な再生成指示を返す。"""
    validator_runner = RecordingValidatorCodexRunner(
        outputs=('{"payload":{"kind":"final","valid":true,"comment":""}}',),
    )
    use_case = _use_case(RecordingReferenceFileValidator(), validator_runner)

    result = use_case.validate(
        (
            '{"payload":{"kind":"final","answers":[{"text":"回答",'
            '"references":[{"source_type":"pdf","locator":{"path":"manual.pdf",'
            '"start_page":1,"end_page":1}}]}]}}'
        ),
        retry_count=0,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.regeneration_instruction == (
        "参照元のパスが不正なため、この回答は採用できません。\n"
        "以下のパス指定が間違っています。\n"
        "- manual.pdf\n"
        "参照元の locator.path は、必ず既存の実PDFファイルへのパスを指す "
        "`readonly/... .pdf` 形式にしてください。\n"
        "回答本文は前回同様にユーザ質問へ完全に回答し、"
        "参照元だけを正しいPDFパスへ修正して最終JSONを再出力してください。"
    )
    assert validator_runner.prompts == []


def test_validate_answer_returns_regeneration_for_reference_failure() -> None:
    """観点：回答検証UseCaseの参照元検証失敗。確認：valid=falseのcommentを再生成指示にする。"""
    use_case = _use_case(
        RecordingReferenceFileValidator(),
        RecordingValidatorCodexRunner(
            outputs=(
                '{"payload":{"kind":"final","valid":false,'
                '"comment":"2ページの根拠が不足しています。"}}',
            ),
        ),
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=1,
        user_instruction="資料を要約",
        chat_id=uuid7(),
        run_id=uuid7(),
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.regeneration_instruction == "2ページの根拠が不足しています。"


def test_validate_answer_returns_specific_regeneration_for_reference_file_failure() -> (
    None
):
    """観点：回答検証UseCaseの参照元固定検証失敗。確認：参照元PDF固定検証結果を再生成指示にする。"""
    validator_runner = RecordingValidatorCodexRunner(
        outputs=('{"payload":{"kind":"final","valid":true,"comment":""}}',),
    )
    use_case = _use_case(
        RecordingReferenceFileValidator(
            result=ReferenceValidationResult(
                valid=False,
                failure=InvalidReferencePathFailure(("readonly/missing.pdf",)),
            )
        ),
        validator_runner,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=0,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.REGENERATE
    assert "以下のパス指定が間違っています。" in result.regeneration_instruction
    assert "- readonly/missing.pdf" in result.regeneration_instruction
    assert validator_runner.prompts == []


def test_validate_answer_fails_when_retry_limit_reached() -> None:
    """観点：回答検証UseCaseの再生成上限。確認：生成回答の再生成上限到達時は失敗にする。"""
    use_case = _use_case(
        RecordingReferenceFileValidator(),
        RecordingValidatorCodexRunner(
            outputs=(
                '{"payload":{"kind":"final","valid":false,"comment":"根拠不足"}}',
            ),
        ),
        max_retries=2,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=2,
        user_instruction="資料を要約",
        chat_id=uuid7(),
        run_id=uuid7(),
    )

    assert result.status is ValidationStatus.FAILED
    assert result.user_message == "回答の生成に失敗しました。再度お試しください。"
    assert result.candidate is None


def test_validate_answer_retries_validator_output_format_error() -> None:
    """観点：検証用Codex出力固定検証。確認：progress最終出力後に再出力指示でfinalを採用する。"""
    validator_runner = RecordingValidatorCodexRunner(
        outputs=(
            '{"payload":{"kind":"progress","text":"検証しています。"}}',
            '{"payload":{"kind":"final","valid":true,"comment":""}}',
        ),
    )
    timeouts = iter((30, 29))
    use_case = _use_case(
        RecordingReferenceFileValidator(),
        validator_runner,
        validator_max_retries=3,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=0,
        user_instruction="資料を要約",
        chat_id=uuid7(),
        run_id=uuid7(),
        get_timeout_seconds=lambda: next(timeouts),
    )

    assert result.status is ValidationStatus.ACCEPTED
    assert len(validator_runner.prompts) == 2
    assert json.loads(validator_runner.prompts[0])["instruction"] == "資料を要約"
    assert "最終検証結果JSONだけを再出力してください。" in validator_runner.prompts[1]
    assert validator_runner.timeout_seconds == [30, 29]


def test_validate_answer_raises_when_validator_output_retry_limit_reached() -> None:
    """観点：検証用Codex出力固定検証。確認：再出力上限後も形式不正なら例外にする。"""
    validator_runner = RecordingValidatorCodexRunner(
        outputs=(
            '{"payload":{"kind":"progress","text":"1"}}',
            '{"payload":{"kind":"progress","text":"2"}}',
            '{"payload":{"kind":"progress","text":"3"}}',
            '{"payload":{"kind":"progress","text":"4"}}',
        ),
    )
    use_case = _use_case(
        RecordingReferenceFileValidator(),
        validator_runner,
        validator_max_retries=3,
    )

    with pytest.raises(ValidationResultFormatError):
        use_case.validate(
            _valid_answer_json(),
            retry_count=0,
            user_instruction="資料を要約",
            chat_id=uuid7(),
            run_id=uuid7(),
            get_timeout_seconds=lambda: 30,
        )

    assert len(validator_runner.prompts) == 4
    assert validator_runner.prompts[1:] == [validator_runner.prompts[1]] * 3


def test_validate_answer_validator_max_retries_does_not_affect_generation_retry() -> (
    None
):
    """観点：再試行上限の分離。確認：validator.max_retriesは生成回答の再生成上限に影響しない。"""
    use_case = _use_case(
        RecordingReferenceFileValidator(),
        RecordingValidatorCodexRunner(
            outputs=(
                '{"payload":{"kind":"final","valid":false,"comment":"根拠不足"}}',
            ),
        ),
        max_retries=1,
        validator_max_retries=3,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=1,
        user_instruction="資料を要約",
        chat_id=uuid7(),
        run_id=uuid7(),
    )

    assert result.status is ValidationStatus.FAILED


@dataclass(slots=True)
class RecordingReferenceFileValidator:
    """テスト用参照元PDF固定検証境界。"""

    result: ReferenceValidationResult = field(
        default_factory=lambda: ReferenceValidationResult(valid=True)
    )
    validated_candidates: list[ParsedAnswerCandidate] = field(default_factory=list)

    def validate_reference_files(
        self,
        candidate: ParsedAnswerCandidate,
    ) -> ReferenceValidationResult:
        self.validated_candidates.append(candidate)
        return self.result


@dataclass(slots=True)
class RecordingValidatorCodexRunner:
    """テスト用検証Codex 1回実行境界。"""

    outputs: tuple[str, ...]
    emitted_message: str | None = None
    prompts: list[str] = field(default_factory=list)
    timeout_seconds: list[int] = field(default_factory=list)
    session_workdirs: list[Path | None] = field(default_factory=list)
    has_artifact_links_values: list[bool] = field(default_factory=list)

    def run_validation(
        self,
        chat_id: UUID,
        run_id: UUID,
        prompt: str,
        timeout_seconds: int,
        trace_id: str,
        on_intermediate_message: object | None = None,
        session_workdir: Path | None = None,
        has_artifact_links: bool = False,
    ) -> ValidatorCodexRunResult:
        _ = (chat_id, run_id, trace_id)
        self.prompts.append(prompt)
        self.timeout_seconds.append(timeout_seconds)
        self.session_workdirs.append(session_workdir)
        self.has_artifact_links_values.append(has_artifact_links)
        if self.emitted_message is not None and callable(on_intermediate_message):
            on_intermediate_message(self.emitted_message)
        output = self.outputs[len(self.prompts) - 1]
        return ValidatorCodexRunResult(
            conversation_id=f"validator-thread-{len(self.prompts)}",
            intermediate_messages=(),
            final_output_json=output,
        )


def _use_case(
    file_validator: RecordingReferenceFileValidator,
    validator_runner: RecordingValidatorCodexRunner,
    *,
    max_retries: int = 2,
    validator_max_retries: int = 0,
) -> ValidateAnswerUseCase:
    return ValidateAnswerUseCase(
        max_retries=max_retries,
        reference_file_validator=file_validator,
        validator_codex_runner=validator_runner,
        validator_max_retries=validator_max_retries,
    )


def _valid_answer_json() -> str:
    return (
        '{"payload":{"kind":"final","answers":[{"text":"要点はAです。",'
        '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
        '"start_page":2,"end_page":3}}]}]}}'
    )

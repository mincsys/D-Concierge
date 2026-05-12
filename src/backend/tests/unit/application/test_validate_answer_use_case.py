from dataclasses import dataclass, field
from pathlib import Path

from backend.application.ports.codex.dto import ReferenceValidationResult
from backend.application.validation.validate_answer import ValidateAnswerUseCase
from backend.application.validation.validation_status import ValidationStatus
from backend.domain.answer.answer_candidate import (
    InvalidReferencePathFailure,
    ParsedAnswerCandidate,
)


def test_validate_answer_accepts_fixed_and_reference_valid_candidate() -> None:
    """観点：回答検証UseCase。

    確認：固定検証と参照元検証に合格した回答候補を採用可能として返す。
    """
    validator = RecordingReferenceValidator(
        result=ReferenceValidationResult(valid=True)
    )
    use_case = ValidateAnswerUseCase(
        reference_validator=validator,
        max_retries=2,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=0,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.ACCEPTED
    assert result.candidate is not None
    assert result.candidate.blocks[0].markdown == "要点はAです。"
    assert validator.validated_candidates[0].blocks[0].references[0].page_start == 2
    assert validator.user_instructions == ["資料を要約"]


def test_validate_answer_forwards_reference_intermediate_callback() -> None:
    """観点：回答検証UseCaseの検証中間メッセージ。

    確認：参照元検証境界へ検証用Codexの中間メッセージ通知先を引き渡す。
    """
    messages: list[str] = []
    validator = RecordingReferenceValidator(
        result=ReferenceValidationResult(valid=True),
        emitted_message="参照元を確認しています。",
    )
    use_case = ValidateAnswerUseCase(
        reference_validator=validator,
        max_retries=2,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=0,
        user_instruction="資料を要約",
        on_intermediate_message=messages.append,
    )

    assert result.status is ValidationStatus.ACCEPTED
    assert messages == ["参照元を確認しています。"]


def test_validate_answer_returns_regeneration_for_fixed_validation_failure() -> None:
    """観点：回答検証UseCaseの固定検証失敗。

    確認：固定検証に失敗し、再生成上限未満の場合は参照元検証を呼ばず再生成指示を返す。
    """
    validator = RecordingReferenceValidator(
        result=ReferenceValidationResult(valid=True)
    )
    use_case = ValidateAnswerUseCase(
        reference_validator=validator,
        max_retries=2,
    )

    result = use_case.validate(
        '{"answers":[]}',
        retry_count=0,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.REGENERATE
    assert "固定検証" in result.regeneration_instruction
    assert validator.validated_candidates == []


def test_validate_answer_returns_specific_regeneration_for_invalid_paths() -> None:
    """観点：回答検証UseCaseの固定検証失敗。

    確認：参照元path不正時は具体的な再生成指示を返す。
    """
    validator = RecordingReferenceValidator(
        result=ReferenceValidationResult(valid=True)
    )
    use_case = ValidateAnswerUseCase(
        reference_validator=validator,
        max_retries=2,
    )

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
    assert validator.validated_candidates == []


def test_validate_answer_returns_regeneration_for_reference_failure() -> None:
    """観点：回答検証UseCaseの参照元検証失敗。

    確認：参照元検証に失敗し、再生成上限未満の場合はcommentを含む再生成指示を返す。
    """
    use_case = ValidateAnswerUseCase(
        reference_validator=RecordingReferenceValidator(
            result=ReferenceValidationResult(
                valid=False,
                comment="2ページの根拠が不足しています。",
            )
        ),
        max_retries=2,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=1,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.REGENERATE
    assert result.regeneration_instruction == "2ページの根拠が不足しています。"


def test_validate_answer_returns_specific_regeneration_for_reference_file_failure() -> (
    None
):
    """観点：回答検証UseCaseの参照元固定検証失敗。

    確認：参照元検証境界が返す構造化失敗理由から再生成指示を組み立てる。
    """
    use_case = ValidateAnswerUseCase(
        reference_validator=RecordingReferenceValidator(
            result=ReferenceValidationResult(
                valid=False,
                failure=InvalidReferencePathFailure(("readonly/missing.pdf",)),
            )
        ),
        max_retries=2,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=0,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.REGENERATE
    assert "以下のパス指定が間違っています。" in result.regeneration_instruction
    assert "- readonly/missing.pdf" in result.regeneration_instruction


def test_validate_answer_fails_when_retry_limit_reached() -> None:
    """観点：回答検証UseCaseの再生成上限。

    確認：検証失敗が再生成上限に到達した場合は利用者向けエラーを返す。
    """
    use_case = ValidateAnswerUseCase(
        reference_validator=RecordingReferenceValidator(
            result=ReferenceValidationResult(valid=False, comment="根拠不足")
        ),
        max_retries=2,
    )

    result = use_case.validate(
        _valid_answer_json(),
        retry_count=2,
        user_instruction="資料を要約",
    )

    assert result.status is ValidationStatus.FAILED
    assert result.user_message == "回答の生成に失敗しました。再度お試しください。"
    assert result.candidate is None


@dataclass(slots=True)
class RecordingReferenceValidator:
    """テスト用参照元検証境界。"""

    result: ReferenceValidationResult
    emitted_message: str | None = None
    validated_candidates: list[ParsedAnswerCandidate] = field(default_factory=list)
    user_instructions: list[str] = field(default_factory=list)
    timeout_seconds: list[int | None] = field(default_factory=list)

    def validate_references(
        self,
        candidate: ParsedAnswerCandidate,
        user_instruction: str,
        chat_id: object | None = None,
        run_id: object | None = None,
        trace_id: str = "",
        timeout_seconds: int | None = None,
        on_intermediate_message: object | None = None,
        session_workdir: Path | None = None,
        has_artifact_links: bool = False,
    ) -> ReferenceValidationResult:
        """検証対象を記録して固定結果を返す。"""
        _ = (chat_id, run_id, trace_id, session_workdir, has_artifact_links)
        self.validated_candidates.append(candidate)
        self.user_instructions.append(user_instruction)
        self.timeout_seconds.append(timeout_seconds)
        if self.emitted_message is not None and callable(on_intermediate_message):
            on_intermediate_message(self.emitted_message)
        return self.result


def _valid_answer_json() -> str:
    return (
        '{"payload":{"kind":"final","answers":[{"text":"要点はAです。",'
        '"references":[{"source_type":"pdf","locator":{"path":"readonly/manual.pdf",'
        '"start_page":2,"end_page":3}}]}]}}'
    )

import json

from backend.application.validation.validator_prompts import (
    build_validator_prompt,
    build_validator_result_retry_prompt,
)
from backend.domain.answer.answer_candidate import (
    ParsedAnswerBlock,
    ParsedAnswerCandidate,
)
from backend.domain.references.pdf_reference import PdfLocator, PdfReference


def test_build_validator_prompt_uses_validator_specific_shape() -> None:
    """観点：検証用Codex入力。確認：ユーザ指示、回答本文、readonly形式の参照元だけを含める。"""
    candidate = ParsedAnswerCandidate(
        blocks=(
            ParsedAnswerBlock(
                markdown="回答",
                references=(
                    PdfReference(
                        label="manual.pdf",
                        locator=PdfLocator(
                            relative_path="raw/pdf/manual.pdf",
                            page_start=1,
                            page_end=2,
                        ),
                    ),
                ),
            ),
        )
    )

    prompt = build_validator_prompt(
        user_instruction="資料を要約",
        candidate=candidate,
    )

    payload = json.loads(prompt)
    assert payload == {
        "instruction": "資料を要約",
        "answers": [
            {
                "text": "回答",
                "references": [
                    {
                        "label": "manual.pdf",
                        "path": "readonly/raw/pdf/manual.pdf",
                        "page_start": 1,
                        "page_end": 2,
                    }
                ],
            }
        ],
    }
    assert "relative_path" not in prompt
    assert "readonly_path" not in prompt
    assert "blocks" not in prompt
    assert "markdown" not in prompt


def test_build_validator_result_retry_prompt_requests_final_only() -> None:
    """観点：検証用Codex再出力指示。確認：progressではなくfinalだけの再出力を求める。"""
    prompt = build_validator_result_retry_prompt()

    assert '"kind":"final"' in prompt
    assert '"kind":"progress"' in prompt
    assert "最終検証結果JSONだけを再出力してください。" in prompt

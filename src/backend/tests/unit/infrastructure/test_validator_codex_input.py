from backend.domain.answer.answer_candidate import (
    ParsedAnswerBlock,
    ParsedAnswerCandidate,
)
from backend.domain.references.pdf_reference import PdfLocator, PdfReference
from backend.infrastructure.codex.validator_codex_input import (
    build_validator_codex_input,
)


def test_build_validator_codex_input_uses_validator_specific_shape() -> None:
    """観点：検証用Codex入力。確認：ユーザ指示、answers、text、pathだけを検証入力へ渡す。"""
    candidate = ParsedAnswerCandidate(
        blocks=(
            ParsedAnswerBlock(
                markdown="回答本文",
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
        ),
    )

    payload = build_validator_codex_input(
        user_instruction="ユーザ指示",
        candidate=candidate,
    )

    assert payload == {
        "instruction": "ユーザ指示",
        "answers": [
            {
                "text": "回答本文",
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
    assert "blocks" not in payload
    answer_payload = payload["answers"][0]
    assert "markdown" not in answer_payload
    reference_payload = answer_payload["references"][0]
    assert "relative_path" not in reference_payload
    assert "readonly_path" not in reference_payload

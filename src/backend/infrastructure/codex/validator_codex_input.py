from typing import TypedDict

from backend.domain.answer.answer_candidate import (
    ParsedAnswerCandidate,
    codex_visible_reference_path,
)


class ValidatorCodexReferenceInput(TypedDict):
    """検証用Codexへ渡す参照元情報。"""

    label: str
    path: str
    page_start: int
    page_end: int


class ValidatorCodexAnswerInput(TypedDict):
    """検証用Codexへ渡す回答情報。"""

    text: str
    references: list[ValidatorCodexReferenceInput]


class ValidatorCodexInput(TypedDict):
    """検証用Codexへ渡す入力。"""

    instruction: str
    answers: list[ValidatorCodexAnswerInput]


def build_validator_codex_input(
    *,
    user_instruction: str,
    candidate: ParsedAnswerCandidate,
) -> ValidatorCodexInput:
    """検証用Codexの参照元検証入力を組み立てる。"""
    return ValidatorCodexInput(
        instruction=user_instruction,
        answers=[
            ValidatorCodexAnswerInput(
                text=block.markdown,
                references=[
                    ValidatorCodexReferenceInput(
                        label=reference.label,
                        path=codex_visible_reference_path(reference.relative_path),
                        page_start=reference.page_start,
                        page_end=reference.page_end,
                    )
                    for reference in block.references
                ],
            )
            for block in candidate.blocks
        ],
    )

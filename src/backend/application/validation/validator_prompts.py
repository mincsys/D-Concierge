"""検証用Codexへ渡すプロンプトを組み立てる。"""

import json
from typing import TypedDict

from backend.domain.answer.answer_candidate import ParsedAnswerCandidate


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


_VALIDATOR_RESULT_RETRY_PROMPT = (
    "検証結果の最終出力形式が不正なため、この検証結果は採用できません。\n"
    '最終出力は必ず {"payload":{"kind":"final","valid":trueまたはfalse,'
    '"comment":"..."}} 形式にしてください。\n'
    '途中経過を示す {"payload":{"kind":"progress","text":"..."}} は'
    "最終出力として使用できません。\n"
    "直前の検証内容を踏まえて、最終検証結果JSONだけを再出力してください。"
)


def build_validator_prompt(
    *,
    user_instruction: str,
    candidate: ParsedAnswerCandidate,
) -> str:
    """検証用Codexへ渡す初回検証プロンプトを返す。"""
    return json.dumps(
        _build_validator_codex_input(
            user_instruction=user_instruction,
            candidate=candidate,
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_validator_result_retry_prompt() -> str:
    """検証用Codexの最終出力形式が不正だった場合の再出力プロンプトを返す。"""
    return _VALIDATOR_RESULT_RETRY_PROMPT


def _build_validator_codex_input(
    *,
    user_instruction: str,
    candidate: ParsedAnswerCandidate,
) -> ValidatorCodexInput:
    return ValidatorCodexInput(
        instruction=user_instruction,
        answers=[
            ValidatorCodexAnswerInput(
                text=block.markdown,
                references=[
                    ValidatorCodexReferenceInput(
                        label=reference.label,
                        path=reference.codex_visible_path(),
                        page_start=reference.page_start,
                        page_end=reference.page_end,
                    )
                    for reference in block.references
                ],
            )
            for block in candidate.blocks
        ],
    )

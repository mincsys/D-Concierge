"""生成用Codexへ渡すプロンプトを組み立てる。"""

_USER_INSTRUCTION_OPEN_TAG = "<ユーザ指示>"
_USER_INSTRUCTION_CLOSE_TAG = "</ユーザ指示>"
_REVISION_INSTRUCTION_OPEN_TAG = "<検証による修正指示>"
_REVISION_INSTRUCTION_CLOSE_TAG = "</検証による修正指示>"

_REGENERATION_PROMPT_LEAD = (
    "以下のユーザ指示に対する前回回答は検証で不採用になりました。\n"
    "ユーザ指示には完全に回答しつつ、検証による修正指示を反映して回答を再出力してください。"
)


def build_generation_prompt(
    user_instruction: str,
    regeneration_instruction: str | None = None,
) -> str:
    """生成用Codex向けに、ユーザ指示と検証修正指示を明確に分けたpromptを返す。"""
    user_block = (
        f"{_USER_INSTRUCTION_OPEN_TAG}\n"
        f"{user_instruction}\n"
        f"{_USER_INSTRUCTION_CLOSE_TAG}"
    )
    if regeneration_instruction is None or regeneration_instruction.strip() == "":
        return user_block

    revision_block = (
        f"{_REVISION_INSTRUCTION_OPEN_TAG}\n"
        f"{regeneration_instruction}\n"
        f"{_REVISION_INSTRUCTION_CLOSE_TAG}"
    )
    return f"{_REGENERATION_PROMPT_LEAD}\n\n{user_block}\n\n{revision_block}"

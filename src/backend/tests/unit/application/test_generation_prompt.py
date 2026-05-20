from backend.application.execution.generation_prompt import build_generation_prompt


def test_build_generation_prompt_wraps_user_instruction_only() -> None:
    """観点：生成用Codexプロンプト。確認：初回生成ではユーザ指示ブロックだけを渡す。"""
    assert build_generation_prompt("資料を要約してください") == (
        "<ユーザ指示>\n資料を要約してください\n</ユーザ指示>"
    )


def test_build_generation_prompt_wraps_revision_instruction() -> None:
    """観点：生成用Codexプロンプト。確認：再生成時はリード文と検証修正指示を分離する。"""
    assert build_generation_prompt(
        "資料を要約してください",
        "参照元を具体化してください。",
    ) == (
        "以下のユーザ指示に対する前回回答は検証で不採用になりました。\n"
        "ユーザ指示には完全に回答しつつ、検証による修正指示を反映して回答を再出力してください。\n\n"
        "<ユーザ指示>\n"
        "資料を要約してください\n"
        "</ユーザ指示>\n\n"
        "<検証による修正指示>\n"
        "参照元を具体化してください。\n"
        "</検証による修正指示>"
    )


def test_build_generation_prompt_ignores_blank_revision_instruction() -> None:
    """観点：生成用Codexプロンプト。確認：空白だけの修正指示は初回形式として扱う。"""
    assert build_generation_prompt("資料を要約してください", "  \n\t") == (
        "<ユーザ指示>\n資料を要約してください\n</ユーザ指示>"
    )


def test_build_generation_prompt_preserves_instruction_text() -> None:
    """観点：生成用Codexプロンプト。確認：ユーザ指示と修正指示の本文を加工しない。"""
    prompt = build_generation_prompt(
        "  1行目\n2行目  ",
        "  修正1\n修正2  ",
    )

    assert "<ユーザ指示>\n  1行目\n2行目  \n</ユーザ指示>" in prompt
    assert ("<検証による修正指示>\n  修正1\n修正2  \n</検証による修正指示>") in prompt

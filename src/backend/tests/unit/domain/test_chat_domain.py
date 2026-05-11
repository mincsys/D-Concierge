import pytest

from backend.domain.chat.chat_title_policy import ChatTitlePolicy
from backend.domain.chat.user_instruction import (
    InvalidUserInstructionError,
    UserInstruction,
)


def test_user_instruction_strips_input_text() -> None:
    """観点：ユーザ指示値オブジェクト。確認：前後空白を除去して本文を保持する。"""
    instruction = UserInstruction("  C++の移植性を説明してください。\n")

    assert instruction.body == "C++の移植性を説明してください。"


def test_user_instruction_rejects_blank_text() -> None:
    """観点：ユーザ指示値オブジェクト。確認：空白だけの本文を拒否する。"""
    with pytest.raises(InvalidUserInstructionError):
        UserInstruction(" \n\t ")


def test_chat_title_policy_normalizes_and_truncates_title() -> None:
    """観点：チャットタイトル方針。確認：空白正規化後に最大50文字でタイトル化する。"""
    instruction = UserInstruction(
        "  0123456789\n0123456789   0123456789\t0123456789 0123456789XYZ  "
    )

    title = ChatTitlePolicy.make_title(instruction)

    assert title == "0123456789 0123456789 0123456789 0123456789 012345"
    assert len(title) == 50


def test_chat_title_policy_uses_default_when_normalized_title_is_empty() -> None:
    """観点：チャットタイトル方針。確認：正規化後に空の場合は既定タイトルを返す。"""
    assert ChatTitlePolicy.make_title_from_text(" \n\t ") == "新しいチャット"

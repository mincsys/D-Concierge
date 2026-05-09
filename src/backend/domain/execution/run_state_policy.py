from typing import Literal

type RunState = Literal[
    "受付",
    "実行中",
    "検証中",
    "キャンセル要求中",
    "キャンセル済み",
    "完了",
    "エラー",
    "タイムアウト",
]

UNFINISHED_STATES: frozenset[RunState] = frozenset(
    ("受付", "実行中", "検証中", "キャンセル要求中")
)
CANCELABLE_STATES: frozenset[RunState] = frozenset(("受付", "実行中", "検証中"))
TERMINAL_STATES: frozenset[RunState] = frozenset(
    ("キャンセル済み", "完了", "エラー", "タイムアウト")
)


class RunStatePolicy:
    """チャット実行状態の未完了、終端、キャンセル可能条件を判定する。"""

    @staticmethod
    def is_unfinished(state: str) -> bool:
        """状態が未完了状態かどうかを返す。"""
        return state in UNFINISHED_STATES

    @staticmethod
    def is_cancelable(state: str) -> bool:
        """状態が利用者キャンセル可能かどうかを返す。"""
        return state in CANCELABLE_STATES

    @staticmethod
    def is_terminal(state: str) -> bool:
        """状態が終端状態かどうかを返す。"""
        return state in TERMINAL_STATES

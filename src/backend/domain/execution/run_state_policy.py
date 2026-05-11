from backend.domain.execution.run_state import RunState

UNFINISHED_STATES: frozenset[RunState] = frozenset(
    (
        RunState.ACCEPTED,
        RunState.RUNNING,
        RunState.VALIDATING,
        RunState.CANCEL_REQUESTED,
    )
)
CANCELABLE_STATES: frozenset[RunState] = frozenset(
    (RunState.ACCEPTED, RunState.RUNNING, RunState.VALIDATING)
)
TERMINAL_STATES: frozenset[RunState] = frozenset(
    (RunState.CANCELED, RunState.COMPLETED, RunState.ERROR, RunState.TIMED_OUT)
)


class RunStatePolicy:
    """チャット実行状態の未完了、終端、キャンセル可能条件を判定する。"""

    @staticmethod
    def is_unfinished(state: RunState) -> bool:
        """状態が未完了状態かどうかを返す。"""
        return state in UNFINISHED_STATES

    @staticmethod
    def is_cancelable(state: RunState) -> bool:
        """状態が利用者キャンセル可能かどうかを返す。"""
        return state in CANCELABLE_STATES

    @staticmethod
    def is_terminal(state: RunState) -> bool:
        """状態が終端状態かどうかを返す。"""
        return state in TERMINAL_STATES

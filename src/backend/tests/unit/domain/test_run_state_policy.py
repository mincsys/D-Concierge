import pytest

from backend.domain.execution.run_state_policy import RunStatePolicy


@pytest.mark.parametrize("state", ["受付", "実行中", "検証中", "キャンセル要求中"])
def test_unfinished_states_are_detected(state: str) -> None:
    """観点：未完了状態の判定。確認：設計上の4状態だけを未完了として扱う。"""
    assert RunStatePolicy.is_unfinished(state)


@pytest.mark.parametrize("state", ["キャンセル済み", "完了", "エラー", "タイムアウト"])
def test_terminal_states_are_not_unfinished(state: str) -> None:
    """観点：終端状態の判定。確認：終端4状態を未完了として扱わない。"""
    assert not RunStatePolicy.is_unfinished(state)


@pytest.mark.parametrize("state", ["受付", "実行中", "検証中"])
def test_cancelable_states_are_limited_to_active_processing(state: str) -> None:
    """観点：キャンセル可能状態。確認：受付、実行中、検証中だけをキャンセル可能にする。"""
    assert RunStatePolicy.is_cancelable(state)


@pytest.mark.parametrize(
    "state", ["キャンセル要求中", "キャンセル済み", "完了", "エラー", "タイムアウト"]
)
def test_terminal_or_cancel_requested_states_are_not_cancelable(state: str) -> None:
    """観点：キャンセル不可状態。確認：キャンセル要求中と終端状態をキャンセル不可にする。"""
    assert not RunStatePolicy.is_cancelable(state)


@pytest.mark.parametrize("state", ["キャンセル済み", "完了", "エラー", "タイムアウト"])
def test_terminal_states_are_detected(state: str) -> None:
    """観点：終端状態の判定。確認：終端4状態だけを終端として扱う。"""
    assert RunStatePolicy.is_terminal(state)


@pytest.mark.parametrize("state", ["受付", "実行中", "検証中", "キャンセル要求中"])
def test_unfinished_states_are_not_terminal(state: str) -> None:
    """観点：終端状態の判定。確認：未完了4状態を終端として扱わない。"""
    assert not RunStatePolicy.is_terminal(state)

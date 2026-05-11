import pytest

from backend.domain.validation.retry_policy import RetryPolicy


def test_retry_policy_allows_retry_before_limit() -> None:
    """観点：再試行方針。確認：再生成回数が上限未満の場合だけ再試行できる。"""
    policy = RetryPolicy(max_retries=2)

    assert policy.can_retry(0)
    assert policy.can_retry(1)
    assert not policy.can_retry(2)
    assert policy.is_limit_reached(2)


def test_retry_policy_rejects_negative_values() -> None:
    """観点：再試行方針。確認：上限と現在回数に負数を許可しない。"""
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=-1)

    with pytest.raises(ValueError):
        RetryPolicy(max_retries=1).can_retry(-1)

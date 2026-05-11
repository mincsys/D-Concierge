from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """検証失敗時の再生成可否を判断する方針。"""

    max_retries: int

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retriesは0以上である必要があります。")

    def can_retry(self, retry_count: int) -> bool:
        """現在の再生成回数で再生成できるかを返す。"""
        self._validate_retry_count(retry_count)
        return retry_count < self.max_retries

    def is_limit_reached(self, retry_count: int) -> bool:
        """現在の再生成回数が上限に到達しているかを返す。"""
        self._validate_retry_count(retry_count)
        return not self.can_retry(retry_count)

    @staticmethod
    def _validate_retry_count(retry_count: int) -> None:
        if retry_count < 0:
            raise ValueError("retry_countは0以上である必要があります。")

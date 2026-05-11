from contextlib import AbstractContextManager, nullcontext


class NoopTransactionManager:
    """テスト用のTransactionManager。"""

    def transaction(self) -> AbstractContextManager[None]:
        """トランザクション境界だけを表し、何も実行しない。"""
        return nullcontext()

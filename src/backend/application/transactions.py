from contextlib import AbstractContextManager, nullcontext


class NoopTransactionManager:
    """DB副作用を持たない境界向けのTransactionManager。"""

    def transaction(self) -> AbstractContextManager[None]:
        """何も開始せずに作業単位だけを表す。"""
        return nullcontext()

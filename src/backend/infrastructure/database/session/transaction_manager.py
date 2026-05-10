from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.orm import Session, sessionmaker

from backend.shared.errors import AppError, ErrorClass

_NO_ACTIVE_TRANSACTION_MESSAGE = "DBトランザクションが開始されていません。"


class SqlAlchemyTransactionManager:
    """SQLAlchemy Sessionのトランザクション境界を管理する。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._current_session: ContextVar[Session | None] = ContextVar(
            "current_sqlalchemy_session",
            default=None,
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """DBトランザクションを開始し、正常終了時commit、例外時rollbackする。"""
        current_session = self._current_session.get()
        if current_session is not None:
            yield
            return

        session = self._session_factory()
        token = self._current_session.set(session)
        try:
            with session.begin():
                yield
        finally:
            self._current_session.reset(token)
            session.close()

    def current_session(self) -> Session:
        """現在のトランザクションSessionを返す。"""
        session = self._current_session.get()
        if session is None:
            raise AppError(ErrorClass.SYSTEM, _NO_ACTIVE_TRANSACTION_MESSAGE)
        return session

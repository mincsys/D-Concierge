from __future__ import annotations

from types import TracebackType
from typing import Literal

from sqlalchemy.orm import Session


class SqlAlchemyTransactionManager:
    """SQLAlchemy Sessionのcommit/rollback境界。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is None:
            self._session.commit()
        else:
            self._session.rollback()
        return False

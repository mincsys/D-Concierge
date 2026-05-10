from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """DB URLからSQLAlchemy session factoryを生成する。"""
    engine = create_engine(database_url)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def create_transaction_manager(database_url: str) -> SqlAlchemyTransactionManager:
    """DB URLからSQLAlchemy TransactionManagerを生成する。"""
    return SqlAlchemyTransactionManager(
        session_factory=create_session_factory(database_url),
    )

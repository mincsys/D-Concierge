import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.infrastructure.database.models.base import Base
from backend.infrastructure.database.repositories.sqlalchemy_chat_repository import (
    SqlAlchemyChatRepository,
)
from backend.infrastructure.database.session.transaction_manager import (
    SqlAlchemyTransactionManager,
)
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


def test_sqlalchemy_repository_requires_active_transaction() -> None:
    """観点：Repositoryトランザクション境界。確認：外部トランザクションなしの呼び出しを拒否する。"""
    repository, _transaction_manager = _make_repository_and_transaction_manager()

    with pytest.raises(AppError) as error_info:
        repository.list_histories()

    assert error_info.value.error_type is ErrorType.SYSTEM


def test_sqlalchemy_transaction_manager_commits_successful_unit() -> None:
    """観点：TransactionManager。確認：正常終了した作業単位をcommitする。"""
    repository, transaction_manager = _make_repository_and_transaction_manager()

    with transaction_manager.transaction():
        accepted = repository.create_chat_with_first_run("初回")

    with transaction_manager.transaction():
        detail = repository.get_chat_detail(accepted.chat_id)

    assert detail.runs[0].run_id == accepted.run_id
    assert detail.runs[0].user_instruction == "初回"


def test_sqlalchemy_transaction_manager_rolls_back_failed_unit() -> None:
    """観点：TransactionManager。確認：例外発生時はDB更新をrollbackする。"""
    repository, transaction_manager = _make_repository_and_transaction_manager()

    with pytest.raises(RuntimeError):
        with transaction_manager.transaction():
            repository.create_chat_with_first_run("rollback対象")
            raise RuntimeError("rollback")

    with transaction_manager.transaction():
        histories = repository.list_histories()

    assert histories == ()


def _make_repository_and_transaction_manager() -> tuple[
    SqlAlchemyChatRepository, SqlAlchemyTransactionManager
]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    transaction_manager = SqlAlchemyTransactionManager(session_factory=session_factory)
    return (
        SqlAlchemyChatRepository(session_provider=transaction_manager),
        transaction_manager,
    )

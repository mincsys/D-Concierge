from sqlalchemy import text
from sqlalchemy.engine import Engine


def test_integration_database_uses_postgresql(
    integration_database_engine: Engine,
    integration_database_name: str,
) -> None:
    """観点：結合テストDB。確認：PostgreSQLテストDBへ接続している。"""
    with integration_database_engine.connect() as connection:
        dialect_name = connection.dialect.name
        database_name = connection.execute(
            text("select current_database()")
        ).scalar_one()

    assert dialect_name == "postgresql"
    assert database_name == integration_database_name

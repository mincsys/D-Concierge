from __future__ import annotations

import ast
from pathlib import Path

REQUIRED_F001_FILES = (
    Path("src/backend/main.py"),
    Path("src/backend/app/router/registration.py"),
    Path("src/backend/presentation/errors/http.py"),
    Path("src/backend/presentation/rest/dependencies.py"),
    Path("src/backend/application/ports/database/interface.py"),
    Path("src/backend/application/ports/database/dto.py"),
    Path("src/backend/infrastructure/config/loader.py"),
    Path("src/backend/infrastructure/database/models/base.py"),
    Path("src/backend/infrastructure/database/models/user.py"),
    Path("src/backend/infrastructure/database/models/chat.py"),
    Path("src/backend/infrastructure/database/models/answer.py"),
    Path("src/backend/infrastructure/database/session/factory.py"),
    Path("src/backend/infrastructure/database/session/transaction_manager.py"),
    Path("src/backend/infrastructure/database/repositories/account.py"),
    Path("src/backend/infrastructure/database/repositories/chat.py"),
    Path("src/backend/infrastructure/filesystem/path_security.py"),
    Path("src/backend/infrastructure/trace_log/writer.py"),
    Path("src/backend/shared/errors/error_type.py"),
    Path("src/backend/shared/errors/errors.py"),
    Path("src/backend/shared/tracing/trace_id.py"),
    Path("src/backend/shared/user_messages.py"),
)


def test_backend_foundation_files_follow_documented_layout() -> None:
    """
    観点：backend基盤のディレクトリ構成が内部設計に従うこと
    確認：composition root、設定読込、DBモデル、Repository境界、共通エラー、
    trace_id、trace logのF001必須ファイルが配置されること
    """
    missing = tuple(str(path) for path in REQUIRED_F001_FILES if not path.exists())

    assert missing == ()


def test_domain_and_application_layers_do_not_import_concrete_side_effects() -> None:
    """
    観点：アーキテクチャ境界がdomain/applicationから具象副作用へ依存しないこと
    確認：domain層とapplication層のPythonファイルがFastAPI、SQLAlchemy、presentation、infrastructureを直接importしないこと
    """
    forbidden_imports = _find_forbidden_layer_imports()

    assert forbidden_imports == ()


def test_f001_alembic_revision_uses_fixed_ddl() -> None:
    """
    観点：DBマイグレーションが作成時点のDDLを固定して持つこと
    確認：F001初期リビジョンが現在のORM metadata create_all/drop_allへ依存せず、
    op.create_tableとop.create_indexで定義されていること
    """
    revision_path = Path(
        "src/backend/infrastructure/database/migrations/versions/"
        "20260621_0001_f001_foundation.py"
    )

    revision_text = revision_path.read_text(encoding="utf-8")

    assert "Base.metadata" not in revision_text
    assert "create_all" not in revision_text
    assert "drop_all" not in revision_text
    assert "op.create_table" in revision_text
    assert "op.create_index" in revision_text


def _find_forbidden_layer_imports() -> tuple[str, ...]:
    violations = []
    layer_rules = (
        (
            Path("src/backend/domain"),
            ("fastapi", "sqlalchemy", "backend.infrastructure", "backend.presentation"),
        ),
        (
            Path("src/backend/application"),
            ("fastapi", "sqlalchemy", "backend.infrastructure", "backend.presentation"),
        ),
    )

    for layer_dir, forbidden_prefixes in layer_rules:
        if not layer_dir.exists():
            violations.append(f"{layer_dir}: ディレクトリが存在しません")
            continue
        for path in sorted(layer_dir.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for imported_name in _imported_names(tree):
                if imported_name.startswith(forbidden_prefixes):
                    violations.append(f"{path}: {imported_name}")

    return tuple(violations)


def _imported_names(tree: ast.AST) -> tuple[str, ...]:
    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_names.append(node.module)
    return tuple(imported_names)

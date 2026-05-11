import ast
from pathlib import Path

_COMPOSITION_ROOT_PARTS = {"app"}
_COMPOSITION_ROOT_FILES = {"main.py"}

_ALLOWED_LAYER_IMPORTS: dict[str, set[str]] = {
    "presentation": {"presentation", "application", "domain", "shared"},
    "application": {"application", "domain", "shared"},
    "domain": {"domain", "shared"},
    "infrastructure": {"infrastructure", "domain", "shared"},
    "shared": {"shared"},
}


def test_production_code_does_not_depend_on_infrastructure_memory() -> None:
    """観点：application ports整理。

    確認：本番コードがテスト用memory実装へ依存しない。
    """
    backend_root = Path(__file__).resolve().parents[3]
    production_files = [
        path
        for path in backend_root.rglob("*.py")
        if "tests" not in path.relative_to(backend_root).parts
    ]

    violations = [
        path.relative_to(backend_root).as_posix()
        for path in production_files
        if "backend.infrastructure.memory" in path.read_text(encoding="utf-8")
    ]

    assert not (backend_root / "infrastructure" / "memory").exists()
    assert violations == []


def test_production_backend_imports_respect_layer_boundaries() -> None:
    """観点：バックエンド層境界。

    確認：composition root以外のproduction codeは設計された層依存方向だけをimportする。
    """
    backend_root = Path(__file__).resolve().parents[3]
    production_files = [
        path
        for path in backend_root.rglob("*.py")
        if "tests" not in path.relative_to(backend_root).parts
        and not _is_composition_root(path, backend_root)
    ]

    violations: list[str] = []
    for path in production_files:
        source_layer = _backend_layer(path, backend_root)
        if source_layer is None:
            continue
        for imported_module in _backend_imports(path):
            if _is_allowed_import(source_layer, imported_module):
                continue
            violations.append(
                f"{path.relative_to(backend_root).as_posix()}: "
                f"{source_layer} -> {imported_module}"
            )

    assert violations == []


def _is_composition_root(path: Path, backend_root: Path) -> bool:
    relative = path.relative_to(backend_root)
    return (
        relative.parts[0] in _COMPOSITION_ROOT_PARTS
        or relative.name in _COMPOSITION_ROOT_FILES
    )


def _backend_layer(path: Path, backend_root: Path) -> str | None:
    parts = path.relative_to(backend_root).parts
    if not parts:
        return None
    layer = parts[0]
    return layer if layer in _ALLOWED_LAYER_IMPORTS else None


def _backend_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(
                alias.name for alias in node.names if alias.name.startswith("backend.")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.startswith("backend."):
                modules.append(node.module)
    return modules


def _is_allowed_import(source_layer: str, imported_module: str) -> bool:
    if imported_module.startswith("backend.application.ports"):
        allowed_layers = _ALLOWED_LAYER_IMPORTS[source_layer]
        return source_layer == "infrastructure" or "application" in allowed_layers

    imported_parts = imported_module.split(".")
    if len(imported_parts) < 2:
        return True
    imported_layer = imported_parts[1]
    allowed_layers = _ALLOWED_LAYER_IMPORTS[source_layer]
    return imported_layer in allowed_layers

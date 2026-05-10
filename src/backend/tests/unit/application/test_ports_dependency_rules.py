from pathlib import Path


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

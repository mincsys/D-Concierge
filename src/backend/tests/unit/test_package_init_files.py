from pathlib import Path


def test_backend_init_files_are_empty() -> None:
    """観点：パッケージ初期化ファイル。確認：__init__.pyに実装や説明を置かない。"""
    backend_root = Path(__file__).parents[2]
    init_files = sorted(backend_root.rglob("__init__.py"))

    non_empty_files = [
        str(path.relative_to(backend_root.parent))
        for path in init_files
        if path.read_text(encoding="utf-8") != ""
    ]

    assert non_empty_files == []

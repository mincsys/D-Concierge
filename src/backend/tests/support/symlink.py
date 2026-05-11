from pathlib import Path

import pytest


def require_symlink_support(tmp_path: Path, *, target_is_directory: bool) -> None:
    """テスト環境でsymlinkを作成できない場合は対象テストをskipする。"""
    target = tmp_path / "symlink-target"
    link = tmp_path / "symlink-check"
    if target_is_directory:
        target.mkdir()
    else:
        target.write_text("check", encoding="utf-8")
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError:
        pytest.skip("この環境ではsymlink作成権限がありません。")
    finally:
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            link.rmdir()

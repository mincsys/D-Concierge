from __future__ import annotations

from pathlib import Path

import pytest


def test_path_security_resolves_safe_relative_path_under_root(tmp_path: Path) -> None:
    """
    観点：PathSecurityServiceが安全な相対パスだけを許可ルート配下へ解決すること
    確認：POSIX相対パスと許可拡張子が指定された場合、許可ルート配下のPathを返すこと
    """
    from backend.infrastructure.filesystem.path_security import PathSecurityService

    resolved_path = PathSecurityService().resolve_under_root(
        tmp_path,
        "manuals/source.pdf",
        (".pdf",),
    )

    assert resolved_path == (tmp_path / "manuals" / "source.pdf").resolve()


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "/etc/passwd",
        "C:\\secret\\source.pdf",
        "C:/secret/source.pdf",
        "C:secret/source.pdf",
        "\\\\server\\share\\source.pdf",
        "//server/share/source.pdf",
        "https://example.com/source.pdf",
        "file:///tmp/source.pdf",
        "../source.pdf",
        "manuals/../source.pdf",
    ),
)
def test_path_security_rejects_unsafe_reference_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    """
    観点：PathSecurityServiceが設計で禁止された参照形式を拒否すること
    確認：Windows絶対、ドライブ相対、UNC、URL、親ディレクトリ参照がAppErrorになること
    """
    from backend.infrastructure.filesystem.path_security import PathSecurityService
    from backend.shared.errors.errors import AppError

    with pytest.raises(AppError):
        PathSecurityService().resolve_under_root(tmp_path, unsafe_path, (".pdf",))


def test_path_security_rejects_disallowed_suffix(tmp_path: Path) -> None:
    """
    観点：PathSecurityServiceが用途外拡張子を拒否すること
    確認：許可拡張子に含まれない相対パスはAppErrorになること
    """
    from backend.infrastructure.filesystem.path_security import PathSecurityService
    from backend.shared.errors.errors import AppError

    with pytest.raises(AppError):
        PathSecurityService().resolve_under_root(
            tmp_path,
            "manuals/source.exe",
            (".pdf",),
        )


def test_path_security_rejects_symlink_escape(tmp_path: Path) -> None:
    """
    観点：PathSecurityServiceが正規化後の許可ルート逸脱を拒否すること
    確認：許可ルート内のsymlinkが外部ディレクトリを指す場合はAppErrorになること
    """
    from backend.infrastructure.filesystem.path_security import PathSecurityService
    from backend.shared.errors.errors import AppError

    outside_dir = tmp_path.parent / f"{tmp_path.name}_outside"
    outside_dir.mkdir()
    (tmp_path / "linked").symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(AppError):
        PathSecurityService().resolve_under_root(
            tmp_path,
            "linked/source.pdf",
            (".pdf",),
        )

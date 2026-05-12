from pathlib import Path

import pytest

from backend.infrastructure.filesystem.path_security import PathSecurityService
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError


def test_path_security_resolves_relative_file_under_allowed_root(
    tmp_path: Path,
) -> None:
    """観点：パス安全性。確認：許可ルート配下の相対PDFパスだけを解決する。"""
    root = tmp_path / "readonly"
    root.mkdir()
    pdf_path = root / "manual.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    resolved = PathSecurityService.resolve_file(
        root=root,
        relative_path="manual.pdf",
        allowed_suffixes=(".pdf",),
    )

    assert resolved == pdf_path


@pytest.mark.parametrize(
    "relative_path", ["../secret.pdf", "/tmp/secret.pdf", "a/../../x.pdf"]
)
def test_path_security_rejects_paths_outside_allowed_root(
    tmp_path: Path,
    relative_path: str,
) -> None:
    """観点：パス安全性。確認：絶対パスと親ディレクトリ参照を許可しない。"""
    root = tmp_path / "readonly"
    root.mkdir()

    with pytest.raises(AppError) as error_info:
        PathSecurityService.resolve_file(
            root=root,
            relative_path=relative_path,
            allowed_suffixes=(".pdf",),
        )

    assert error_info.value.error_type is ErrorType.FORBIDDEN


def test_path_security_rejects_unexpected_suffix(tmp_path: Path) -> None:
    """観点：パス安全性。確認：許可されていない拡張子を拒否する。"""
    root = tmp_path / "readonly"
    root.mkdir()

    with pytest.raises(AppError) as error_info:
        PathSecurityService.resolve_file(
            root=root,
            relative_path="memo.txt",
            allowed_suffixes=(".pdf",),
        )

    assert error_info.value.error_type is ErrorType.FORBIDDEN


def test_path_security_rejects_null_byte_path(tmp_path: Path) -> None:
    """観点：パス安全性。確認：NUL文字を含むパスを拒否する。"""
    root = tmp_path / "readonly"
    root.mkdir()

    with pytest.raises(AppError) as error_info:
        PathSecurityService.resolve_file(
            root=root,
            relative_path="manual.pdf\x00.txt",
            allowed_suffixes=(".pdf",),
        )

    assert error_info.value.error_type is ErrorType.FORBIDDEN

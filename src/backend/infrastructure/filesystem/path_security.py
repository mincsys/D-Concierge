from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:")
URL_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True, slots=True)
class PathSecurityService:
    """許可ルート配下の相対パスだけを実ファイル参照へ変換する。"""

    def resolve_under_root(
        self,
        root: Path,
        relative_path: str,
        allowed_suffixes: tuple[str, ...] = (),
    ) -> Path:
        normalized_path = self._normalize_relative_path(
            relative_path,
            allowed_suffixes,
        )
        root_path = root.resolve()
        candidate = (root_path / normalized_path).resolve()
        if candidate != root_path and root_path not in candidate.parents:
            self._raise_forbidden_path(relative_path)
        return candidate

    def _normalize_relative_path(
        self,
        relative_path: str,
        allowed_suffixes: tuple[str, ...],
    ) -> PurePosixPath:
        if self._is_forbidden_raw_path(relative_path):
            self._raise_forbidden_path(relative_path)
        normalized = relative_path.replace("\\", "/")
        posix_path = PurePosixPath(normalized)
        if (
            not normalized
            or posix_path.is_absolute()
            or any(part in ("", ".", "..") for part in posix_path.parts)
        ):
            self._raise_forbidden_path(relative_path)
        if allowed_suffixes and posix_path.suffix not in allowed_suffixes:
            self._raise_forbidden_path(relative_path)
        return posix_path

    def _is_forbidden_raw_path(self, relative_path: str) -> bool:
        return (
            "\x00" in relative_path
            or "://" in relative_path
            or relative_path.startswith(("\\\\", "//"))
            or DRIVE_PATH_PATTERN.match(relative_path) is not None
            or URL_SCHEME_PATTERN.match(relative_path) is not None
        )

    def _raise_forbidden_path(self, relative_path: str) -> None:
        raise AppError(
            error_type=ErrorType.FORBIDDEN,
            trace=False,
            diagnostic_message=f"許可されないパスです: {relative_path}",
        )

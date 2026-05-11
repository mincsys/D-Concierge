from pathlib import Path

from backend.shared.error_class import ErrorClass
from backend.shared.errors import AppError


class PathSecurityService:
    """許可ルート配下の相対ファイルパスだけを解決する。"""

    @staticmethod
    def resolve_file(
        root: Path,
        relative_path: str,
        allowed_suffixes: tuple[str, ...],
    ) -> Path:
        """相対パスを許可ルート配下のファイルとして解決する。"""
        if "\x00" in relative_path:
            raise AppError(ErrorClass.FORBIDDEN, "指定されたファイルは表示できません。")

        requested_path = Path(relative_path)
        if requested_path.is_absolute():
            raise AppError(ErrorClass.FORBIDDEN, "指定されたファイルは表示できません。")

        if requested_path.suffix.lower() not in allowed_suffixes:
            raise AppError(ErrorClass.FORBIDDEN, "指定されたファイルは表示できません。")

        resolved_root = root.resolve()
        resolved_file = (resolved_root / requested_path).resolve()
        if not resolved_file.is_relative_to(resolved_root):
            raise AppError(ErrorClass.FORBIDDEN, "指定されたファイルは表示できません。")

        return resolved_file

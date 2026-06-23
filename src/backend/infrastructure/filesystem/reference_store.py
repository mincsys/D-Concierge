from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.application.ports.filesystem.dto import OpenedReferenceFile
from backend.infrastructure.filesystem.path_security import PathSecurityService
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError

REFERENCE_PDF_SUFFIXES = (".pdf",)


@dataclass(frozen=True, slots=True)
class FileReferenceStore:
    """共有データソース内PDFを配信用ファイルとして解決する。"""

    data_source_root: Path
    path_security: PathSecurityService = field(default_factory=PathSecurityService)

    def open_reference_file(self, relative_path: str) -> OpenedReferenceFile:
        file_path = self.path_security.resolve_under_root(
            self.data_source_root,
            relative_path,
            REFERENCE_PDF_SUFFIXES,
        )
        if not file_path.is_file():
            raise AppError(
                error_type=ErrorType.NOT_FOUND,
                trace=False,
                diagnostic_message="参照元PDFファイルが見つかりません。",
            )
        try:
            with file_path.open("rb"):
                pass
        except OSError as error:
            raise AppError(
                error_type=ErrorType.SYSTEM,
                trace=True,
                diagnostic_message="参照元PDFファイルを読み取れません。",
                cause=error,
            ) from error
        return OpenedReferenceFile(file_path=file_path, mime_type="application/pdf")

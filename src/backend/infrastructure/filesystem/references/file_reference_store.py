from pathlib import Path

from backend.application.ports.filesystem.dto import OpenedReferenceFile
from backend.infrastructure.filesystem.path_security import PathSecurityService
from backend.shared.error_class import ErrorClass
from backend.shared.errors import AppError


class FileReferenceStore:
    """共有データソース内のPDF参照元ファイルを開く。"""

    def __init__(self, datasource_dir: Path) -> None:
        self._datasource_dir = datasource_dir

    def open_reference_file(self, relative_path: str) -> OpenedReferenceFile:
        """共有データソース領域内のPDFを配信用に開く。"""
        path = PathSecurityService.resolve_file(
            root=self._datasource_dir,
            relative_path=relative_path,
            allowed_suffixes=(".pdf",),
        )
        if not path.exists() or not path.is_file():
            raise AppError(ErrorClass.NOT_FOUND, "対象の参照元が見つかりません。")
        return OpenedReferenceFile(path=path, mime_type="application/pdf")

from dataclasses import dataclass
from pathlib import PurePosixPath

from backend.domain.references.source_type import SourceType

_CODEX_READONLY_DIR = "readonly"


class InvalidPdfReferenceError(ValueError):
    """PDF参照元が成立しないことを示すドメインエラー。"""


@dataclass(frozen=True, slots=True)
class PdfLocator:
    """共有データソース相対pathとPDFページ範囲。"""

    relative_path: str
    page_start: int
    page_end: int

    def __post_init__(self) -> None:
        if "\x00" in self.relative_path or "\\" in self.relative_path:
            raise InvalidPdfReferenceError("PDF参照元pathが不正です。")
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or len(path.parts) == 0
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.lower() != ".pdf"
        ):
            raise InvalidPdfReferenceError("PDF参照元pathが不正です。")
        if self.page_start < 1 or self.page_end < self.page_start:
            raise InvalidPdfReferenceError("PDF参照元ページ範囲が不正です。")

    def codex_visible_path(self) -> str:
        """Codex作業領域上のreadonly付きpathを返す。"""
        return PurePosixPath(_CODEX_READONLY_DIR, self.relative_path).as_posix()


@dataclass(frozen=True, slots=True)
class PdfReference:
    """PDF参照元。"""

    label: str
    locator: PdfLocator

    def __post_init__(self) -> None:
        if self.label.strip() == "" or "/" in self.label or "\\" in self.label:
            raise InvalidPdfReferenceError("PDF参照元ラベルが不正です。")

    @classmethod
    def from_locator(cls, locator: PdfLocator) -> "PdfReference":
        """locatorのファイル名から表示ラベルを作る。"""
        return cls(label=PurePosixPath(locator.relative_path).name, locator=locator)

    @property
    def source_type(self) -> SourceType:
        """参照元種別。"""
        return SourceType.PDF

    @property
    def relative_path(self) -> str:
        """共有データソース相対path。"""
        return self.locator.relative_path

    @property
    def page_start(self) -> int:
        """開始ページ番号。"""
        return self.locator.page_start

    @property
    def page_end(self) -> int:
        """終了ページ番号。"""
        return self.locator.page_end

    def codex_visible_path(self) -> str:
        """Codex作業領域上のreadonly付きpathを返す。"""
        return self.locator.codex_visible_path()

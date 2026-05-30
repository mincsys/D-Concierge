import pytest

from backend.domain.references.pdf_reference import (
    InvalidPdfReferenceError,
    PdfLocator,
    PdfReference,
)
from backend.domain.references.source_type import SourceType


def test_pdf_locator_keeps_data_source_relative_pdf_path_and_pages() -> None:
    """観点：PDF locator。確認：共有データソース相対pathとページ範囲を保持する。"""
    locator = PdfLocator(relative_path="raw/pdf/manual.pdf", page_start=1, page_end=3)

    assert locator.relative_path == "raw/pdf/manual.pdf"
    assert locator.page_start == 1
    assert locator.page_end == 3
    assert locator.codex_visible_path() == "data_source/raw/pdf/manual.pdf"


def test_pdf_locator_rejects_invalid_paths_and_page_ranges() -> None:
    """観点：PDF locator。

    確認：絶対path、親参照、PDF以外、成立しないページ範囲を拒否する。
    """
    invalid_values = [
        ("/raw/pdf/manual.pdf", 1, 1),
        ("../manual.pdf", 1, 1),
        ("raw\\pdf\\manual.pdf", 1, 1),
        ("raw/pdf/manual.html", 1, 1),
        ("raw/pdf/manual.pdf", 0, 1),
        ("raw/pdf/manual.pdf", 3, 2),
    ]

    for relative_path, page_start, page_end in invalid_values:
        with pytest.raises(InvalidPdfReferenceError):
            PdfLocator(
                relative_path=relative_path,
                page_start=page_start,
                page_end=page_end,
            )


def test_pdf_reference_derives_safe_label_from_locator() -> None:
    """観点：PDF参照元。確認：PDF種別を固定し、表示ラベルをファイル名から作る。"""
    reference = PdfReference.from_locator(
        PdfLocator(relative_path="raw/pdf/manual.pdf", page_start=2, page_end=4)
    )

    assert reference.source_type is SourceType.PDF
    assert reference.label == "manual.pdf"
    assert reference.relative_path == "raw/pdf/manual.pdf"
    assert reference.page_start == 2
    assert reference.page_end == 4

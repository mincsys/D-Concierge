from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from backend.application.ports.codex.dto import ReferenceValidationResult


@dataclass(frozen=True, slots=True)
class PdfReferenceFileValidator:
    """共有データソース内のPDF参照元を検証する。"""

    data_source_dir: Path

    def validate_pdf_reference(
        self,
        path: str,
        page_start: int,
        page_end: int,
    ) -> ReferenceValidationResult:
        candidate = self.data_source_dir / path
        try:
            resolved_root = self.data_source_dir.resolve()
            resolved_candidate = candidate.resolve()
        except OSError:
            return ReferenceValidationResult(
                path=path,
                page_start=page_start,
                page_end=page_end,
                exists=False,
                readable=False,
                page_count=0,
            )
        if (
            not resolved_candidate.is_relative_to(resolved_root)
            or not candidate.is_file()
        ):
            return ReferenceValidationResult(
                path=path,
                page_start=page_start,
                page_end=page_end,
                exists=False,
                readable=False,
                page_count=0,
            )
        try:
            reader = PdfReader(resolved_candidate)
            page_count = len(reader.pages)
        except Exception:
            return ReferenceValidationResult(
                path=path,
                page_start=page_start,
                page_end=page_end,
                exists=True,
                readable=False,
                page_count=0,
            )
        return ReferenceValidationResult(
            path=path,
            page_start=page_start,
            page_end=page_end,
            exists=True,
            readable=True,
            page_count=page_count,
        )

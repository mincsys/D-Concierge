#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath

SECTION_TAG_PATTERN = re.compile(r"</?section\b[^>]*>", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract matching HTML page sections for an IPA Books PDF reference."
    )
    parser.add_argument("--pdf-path", required=True)
    parser.add_argument("--start-page", required=True, type=int)
    parser.add_argument("--end-page", required=True, type=int)
    args = parser.parse_args()

    try:
        html_path = html_path_for_pdf(args.pdf_path)
        if args.start_page < 1 or args.end_page < args.start_page:
            raise ValueError("invalid page range")
        html = html_path.read_text(encoding="utf-8")
        fragments = [
            extract_page_section(html, page_number)
            for page_number in range(args.start_page, args.end_page + 1)
        ]
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write("\n".join(fragments))
    if fragments:
        sys.stdout.write("\n")
    return 0


def html_path_for_pdf(pdf_path: str) -> Path:
    if "\x00" in pdf_path:
        raise ValueError("pdf path contains NUL")

    normalized_pdf_path = pdf_path.replace("\\", "/")
    raw_path = Path(normalized_pdf_path)
    if raw_path.is_absolute():
        raise ValueError("pdf path must be relative")

    posix_path = PurePosixPath(normalized_pdf_path)
    parts = posix_path.parts
    if not parts or parts[0] != "data_source":
        raise ValueError("pdf path must start with data_source/")
    if ".." in parts:
        raise ValueError("pdf path must not contain parent directory references")
    if posix_path.suffix.lower() != ".pdf":
        raise ValueError("pdf path must end with .pdf")

    if len(parts) >= 5 and parts[1:4] == ("IPA_books", "raw", "pdf"):
        document_name = PurePosixPath(*parts[4:]).with_suffix("").as_posix()
    elif len(parts) == 2:
        document_name = posix_path.with_suffix("").name
    else:
        raise ValueError(
            "pdf path must be data_source/IPA_books/raw/pdf/<document>.pdf"
        )

    html_path = Path("data_source") / "IPA_books" / "html" / document_name / "index.html"
    if not html_path.is_file():
        raise ValueError(f"matching HTML not found: {html_path.as_posix()}")
    return html_path


def extract_page_section(html: str, page_number: int) -> str:
    start_tag = find_page_start_tag(html, page_number)
    if start_tag is None:
        raise ValueError(f"HTML page not found: page-{page_number}")

    depth = 0
    for match in SECTION_TAG_PATTERN.finditer(html, start_tag.start()):
        tag = match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[start_tag.start() : match.end()]
        else:
            depth += 1

    raise ValueError(f"HTML page section is not closed: page-{page_number}")


def find_page_start_tag(html: str, page_number: int) -> re.Match[str] | None:
    page_id = f"page-{page_number}"
    opening_section_pattern = re.compile(r"<section\b[^>]*>", re.IGNORECASE)
    id_pattern = re.compile(
        rf"""\bid\s*=\s*(["']){re.escape(page_id)}\1""",
        re.IGNORECASE,
    )
    for match in opening_section_pattern.finditer(html):
        if id_pattern.search(match.group(0)):
            return match
    return None


if __name__ == "__main__":
    raise SystemExit(main())

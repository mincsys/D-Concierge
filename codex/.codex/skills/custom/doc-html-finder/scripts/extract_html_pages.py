"""HTML化された文書から指定ページの section を抽出する。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def configure_standard_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def resolve_index_html(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_dir():
        path = path / "index.html"
    if not path.exists():
        raise FileNotFoundError(f"index.html が見つかりません: {path}")
    if path.name.lower() != "index.html":
        raise ValueError("文書パスには index.html または文書ディレクトリを指定してください。")
    return path


def parse_pages(value: str) -> list[int]:
    pages: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return sorted(page for page in pages if page > 0)


def find_page_sections(text: str) -> dict[int, str]:
    starts = list(
        re.finditer(
            r'(?:<hr>\s*)?<section\s+class="page"\s+id="page-(?P<page>\d+)">',
            text,
            re.IGNORECASE,
        )
    )
    sections: dict[int, str] = {}
    for index, match in enumerate(starts):
        page = int(match.group("page"))
        section_start = match.start()
        section_end = starts[index + 1].start() if index + 1 < len(starts) else text.find("</main>", match.end())
        if section_end == -1:
            section_end = len(text)
        section = text[section_start:section_end].strip()
        if section.startswith("<hr>"):
            section = re.sub(r"^<hr>\s*", "", section, count=1).strip()
        sections[page] = section
    return sections


def expand_context(pages: list[int], context: int) -> list[int]:
    expanded: set[int] = set()
    for page in pages:
        expanded.update(range(max(1, page - context), page + context + 1))
    return sorted(expanded)


def main() -> int:
    configure_standard_streams()

    parser = argparse.ArgumentParser(
        description="HTML化された文書の index.html から指定 PDF ページの section を抽出します。"
    )
    parser.add_argument("document", help="index.html または html/<文書名> ディレクトリ")
    parser.add_argument("pages", help="ページ指定。例: 34 または 34,35,36 または 34-36")
    parser.add_argument("--context", type=int, default=0, help="各ページの前後に追加するページ数")
    args = parser.parse_args()

    index_html = resolve_index_html(args.document)
    requested_pages = expand_context(parse_pages(args.pages), max(0, args.context))
    text = index_html.read_text(encoding="utf-8")
    sections = find_page_sections(text)

    missing = [page for page in requested_pages if page not in sections]
    for page in requested_pages:
        section = sections.get(page)
        if section:
            sys.stdout.write(section)
            sys.stdout.write("\n")

    if missing:
        sys.stderr.write(f"見つからないページ: {','.join(map(str, missing))}\n")
    return 1 if missing and not any(page in sections for page in requested_pages) else 0


if __name__ == "__main__":
    raise SystemExit(main())

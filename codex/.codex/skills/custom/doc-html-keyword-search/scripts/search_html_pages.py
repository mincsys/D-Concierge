"""文書HTMLをページ単位でキーワード検索し、結果をJSONで出力する。"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Iterable


def configure_standard_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def collect_index_files(target: Path) -> list[Path]:
    if target.is_file():
        if target.name.lower() != "index.html":
            raise ValueError("ファイルを指定する場合は index.html を指定してください。")
        return [target]

    if not target.exists():
        raise FileNotFoundError(f"指定パスが見つかりません: {target}")

    direct_index = target / "index.html"
    if direct_index.exists():
        return [direct_index]

    index_files = sorted(path for path in target.glob("*/index.html") if path.is_file())
    if not index_files:
        raise FileNotFoundError(f"検索対象の index.html が見つかりません: {target}")
    return index_files


def extract_page_sections(text: str) -> Iterable[tuple[int, str]]:
    starts = list(
        re.finditer(
            r'(?:<hr>\s*)?<section\s+class="page"\s+id="page-(?P<page>\d+)">',
            text,
            re.IGNORECASE,
        )
    )
    for index, match in enumerate(starts):
        page = int(match.group("page"))
        section_start = match.start()
        section_end = starts[index + 1].start() if index + 1 < len(starts) else text.find("</main>", match.end())
        if section_end == -1:
            section_end = len(text)
        yield page, text[section_start:section_end]


def html_to_text(section: str) -> str:
    def image_alt(match: re.Match[str]) -> str:
        tag = match.group(0)
        alt_match = re.search(r'\balt\s*=\s*(["\'])(?P<alt>.*?)\1', tag, re.IGNORECASE | re.DOTALL)
        return f" {alt_match.group('alt')} " if alt_match else " "

    section = re.sub(r"<img\b[^>]*>", image_alt, section, flags=re.IGNORECASE | re.DOTALL)
    section = re.sub(r"<script\b.*?</script>", " ", section, flags=re.IGNORECASE | re.DOTALL)
    section = re.sub(r"<style\b.*?</style>", " ", section, flags=re.IGNORECASE | re.DOTALL)
    section = re.sub(r"<[^>]+>", " ", section)
    section = html.unescape(section)
    return re.sub(r"\s+", " ", section).strip()


def compile_patterns(terms: list[str], use_regex: bool, ignore_case: bool) -> list[tuple[str, re.Pattern[str]]]:
    flags = re.IGNORECASE if ignore_case else 0
    patterns = []
    for term in terms:
        pattern_text = term if use_regex else re.escape(term)
        try:
            patterns.append((term, re.compile(pattern_text, flags)))
        except re.error as exc:
            raise ValueError(f"正規表現が不正です: {term}: {exc}") from exc
    return patterns


def make_snippet(text: str, start: int, end: int, context_chars: int, max_chars: int) -> str:
    left = max(0, start - context_chars)
    right = min(len(text), end + context_chars)
    if right - left > max_chars:
        right = min(len(text), left + max_chars)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    return f"{prefix}{text[left:right]}{suffix}"


def search_page(
    text: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    mode: str,
    context_chars: int,
    max_snippets: int,
    max_snippet_chars: int,
) -> dict[str, object] | None:
    term_matches: dict[str, list[re.Match[str]]] = {}
    for term, pattern in patterns:
        matches = list(pattern.finditer(text))
        if matches:
            term_matches[term] = matches

    if mode == "and" and len(term_matches) != len(patterns):
        return None
    if mode == "or" and not term_matches:
        return None

    all_matches = sorted(
        (match for matches in term_matches.values() for match in matches),
        key=lambda match: (match.start(), match.end()),
    )
    snippets = [
        make_snippet(text, match.start(), match.end(), context_chars, max_snippet_chars)
        for match in all_matches[:max_snippets]
    ]
    return {
        "hit_count": len(all_matches),
        "matched_terms": list(term_matches.keys()),
        "snippets": snippets,
    }


def main() -> int:
    configure_standard_streams()

    parser = argparse.ArgumentParser(
        description="html/*/index.html をページ単位で検索し、ヒットした文書とPDFページ番号をJSONで返します。"
    )
    parser.add_argument("target", help="html ルート、文書ディレクトリ、または index.html")
    parser.add_argument("terms", nargs="+", help="検索ワード。--regex 指定時は正規表現として扱います。")
    parser.add_argument("--regex", action="store_true", help="検索ワードを正規表現として扱う")
    parser.add_argument("--mode", choices=["and", "or"], default="or", help="複数語の一致条件")
    parser.add_argument("--ignore-case", action="store_true", help="大文字小文字を区別しない")
    parser.add_argument("--context-chars", type=int, default=40, help="抜粋の前後文字数")
    parser.add_argument("--max-snippets", type=int, default=3, help="ページごとの最大抜粋数")
    parser.add_argument("--max-snippet-chars", type=int, default=240, help="抜粋1件あたりの最大文字数")
    parser.add_argument("--max-results", type=int, default=30, help="results に返す最大件数")
    args = parser.parse_args()

    try:
        index_files = collect_index_files(Path(args.target))
        patterns = compile_patterns(args.terms, args.regex, args.ignore_case)
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    results: list[dict[str, object]] = []
    for index_file in index_files:
        source = index_file.read_text(encoding="utf-8")
        for page, section in extract_page_sections(source):
            page_text = html_to_text(section)
            page_result = search_page(
                page_text,
                patterns,
                args.mode,
                max(0, args.context_chars),
                max(1, args.max_snippets),
                max(1, args.max_snippet_chars),
            )
            if not page_result:
                continue
            results.append(
                {
                    "document": index_file.parent.name,
                    "path": relative_path(index_file),
                    "page": page,
                    **page_result,
                }
            )

    max_results = max(0, args.max_results)
    returned_results = results[:max_results]
    output = {
        "query": args.terms,
        "regex": args.regex,
        "mode": args.mode,
        "ignore_case": args.ignore_case,
        "max_results": max_results,
        "match_count": len(results),
        "returned_count": len(returned_results),
        "results": returned_results,
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

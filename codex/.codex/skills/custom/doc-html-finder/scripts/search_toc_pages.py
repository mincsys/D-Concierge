"""HTML化された文書の目次からページ候補を検索する。"""

from __future__ import annotations

import argparse
import html
import json
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


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def extract_toc_rows(text: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    pattern = re.compile(
        r'<div\s+class="toc-row">\s*'
        r'<span\s+class="toc-title">(?P<title>.*?)</span>\s*'
        r'<span\s+class="toc-page">(?P<page>\d+)</span>\s*'
        r"</div>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        rows.append(
            {
                "title": strip_tags(match.group("title")),
                "page": int(match.group("page")),
            }
        )
    return rows


def score_title(title: str, terms: list[str]) -> tuple[int, list[str]]:
    normalized_title = normalize(title)
    matched: list[str] = []
    score = 0
    for term in terms:
        normalized_term = normalize(term)
        if not normalized_term:
            continue
        if normalized_term in normalized_title:
            matched.append(term)
            score += max(1, len(normalized_term))
    return score, matched


def main() -> int:
    configure_standard_streams()

    parser = argparse.ArgumentParser(
        description="HTML化された文書の toc-row から検索語に該当するページ候補を JSON で返します。"
    )
    parser.add_argument("document", help="index.html または html/<文書名> ディレクトリ")
    parser.add_argument("query", help="主検索語")
    parser.add_argument("--terms", nargs="*", default=[], help="追加検索語")
    parser.add_argument("--limit", type=int, default=20, help="返す最大候補数")
    args = parser.parse_args()

    index_html = resolve_index_html(args.document)
    text = index_html.read_text(encoding="utf-8")
    rows = extract_toc_rows(text)
    terms = [args.query, *args.terms]

    matches = []
    for row in rows:
        score, matched_terms = score_title(str(row["title"]), terms)
        if score <= 0:
            continue
        matches.append(
            {
                "document": index_html.parent.name,
                "path": str(index_html),
                "title": row["title"],
                "page": row["page"],
                "score": score,
                "matched_terms": matched_terms,
            }
        )

    matches.sort(key=lambda item: (-int(item["score"]), int(item["page"]), str(item["title"])))
    result = {
        "query": args.query,
        "terms": terms,
        "match_count": len(matches),
        "matches": matches[: max(0, args.limit)],
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""IPA Books の meta JSON から文書概要と目次を Markdown で出力する。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict


class TocItem(TypedDict, total=False):
    title: str
    children: list["TocItem"]


class MetaJson(TypedDict, total=False):
    summary: str
    table_of_contents: list[TocItem]


def configure_standard_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def resolve_meta_files(path_text: str) -> list[Path]:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(f"meta JSON パスが見つかりません: {path}")
    if path.is_file():
        if path.suffix.lower() != ".json":
            raise ValueError("meta JSON ファイルまたは meta ディレクトリを指定してください。")
        return [path]
    files = sorted(path.glob("*.json"), key=lambda item: item.stem)
    if not files:
        raise FileNotFoundError(f"meta JSON が見つかりません: {path}")
    return files


def load_meta_json(path: Path) -> MetaJson:
    with path.open(encoding="utf-8") as file:
        loaded = json.load(file)
    if not isinstance(loaded, dict):
        raise ValueError(f"meta JSON のルートがオブジェクトではありません: {path}")
    return loaded


def write_toc_items(items: list[TocItem], indent_level: int = 0) -> None:
    indent = "  " * indent_level
    for item in items:
        title = item.get("title")
        if title:
            sys.stdout.write(f"{indent}- {title}\n")
        children = item.get("children", [])
        if children:
            write_toc_items(children, indent_level + 1)


def write_meta_markdown(meta_files: list[Path]) -> None:
    sys.stdout.write("# IPA Books メタ情報一覧\n\n")
    for index, path in enumerate(meta_files):
        if index:
            sys.stdout.write("\n")
        meta = load_meta_json(path)
        sys.stdout.write(f"## {path.stem}\n\n")

        summary = meta.get("summary")
        if summary:
            sys.stdout.write("### 概要\n")
            sys.stdout.write(summary.strip())
            sys.stdout.write("\n\n")

        toc_items = meta.get("table_of_contents", [])
        if toc_items:
            sys.stdout.write("### 目次\n")
            write_toc_items(toc_items)
            sys.stdout.write("\n")


def main() -> int:
    configure_standard_streams()

    parser = argparse.ArgumentParser(
        description="IPA Books の meta JSON から文書概要と目次を Markdown で出力します。"
    )
    parser.add_argument("meta", help="readonly/IPA_books/raw/meta ディレクトリまたは meta JSON ファイル")
    args = parser.parse_args()

    try:
        write_meta_markdown(resolve_meta_files(args.meta))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

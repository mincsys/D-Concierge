---
name: doc-html-keyword-search
description: Search structured document HTML files under readonly/IPA_books/raw/*/index.html by keyword or optional regular expression, page by page. Use when Codex needs to return a JSON list of documents and PDF page numbers where specific search words appear, without doing semantic passage selection.
---

# Doc HTML Keyword Search

## 概要

`readonly/IPA_books/raw/*/index.html` の文書 HTML を `<section class="page" id="page-N">` 単位で検索し、検索ワードにヒットした文書名と PDF ページ番号の一覧を JSON で返す。

このスキルは機械的なキーワード検索用。質問意図に合う本文を解釈して探す場合は `doc-html-finder` を使う。

## 使い方

Python は必ず `uv run python` で実行する。

複数文書を横断検索する:

```powershell
uv run python "$CODEX_HOME/skills/custom/doc-html-keyword-search/scripts/search_html_pages.py" readonly/IPA_books/raw コーディング規約
```

正規表現で検索する:

```powershell
uv run python "$CODEX_HOME/skills/custom/doc-html-keyword-search/scripts/search_html_pages.py" readonly/IPA_books/raw "コーディング.*規約" --regex
```

複数語をすべて含むページだけ返す:

```powershell
uv run python "$CODEX_HOME/skills/custom/doc-html-keyword-search/scripts/search_html_pages.py" readonly/IPA_books/raw 安全 要求 --mode and
```

入力パスには以下を指定できる。

- `readonly/IPA_books/raw` ルート
- `readonly/IPA_books/raw/<文書名>` の文書ディレクトリ
- `readonly/IPA_books/raw/<文書名>/index.html`

## 検索仕様

- 標準はリテラル部分一致検索。
- `--regex`: デフォルト `false`。指定時のみ検索ワードを正規表現として扱う。
- `--mode`: デフォルト `or`。`or` は検索語のいずれかが含まれるページを返し、`and` は検索語すべてが同一ページに含まれる場合だけ返す。
- `--ignore-case`: デフォルト `false`。指定時は大文字小文字を区別しない。
- `--context-chars`: デフォルト `40`。抜粋でヒット箇所の前後に含める文字数。
- `--max-snippets`: デフォルト `3`。ページごとに返す抜粋の最大件数。
- `--max-snippet-chars`: デフォルト `240`。抜粋 1 件あたりの最大文字数。
- `--max-results`: デフォルト `30`。`results` に返す最大件数。`match_count` は制限前の全ヒットページ数を示す。
- HTML タグは検索前に除去し、HTML 実体参照は `html.unescape()` で戻す。
- `<img alt="...">` の `alt` テキストは検索対象に含める。
- 画像内文字は OCR しない。

## JSON 出力

標準出力は JSON のみとする。

```json
{
  "query": ["検索語"],
  "regex": false,
  "mode": "or",
  "ignore_case": false,
  "max_results": 30,
  "match_count": 1,
  "returned_count": 1,
  "results": [
    {
      "document": "文書名",
      "path": "readonly/IPA_books/raw/文書名/index.html",
      "page": 34,
      "hit_count": 2,
      "matched_terms": ["検索語"],
      "snippets": ["...検索語を含む短い抜粋..."]
    }
  ]
}
```

## 回答時の扱い

- ユーザが JSON を求めている場合は、スクリプト出力をそのまま返す。
- ユーザが一覧だけを求めている場合は、JSON の `results` から文書名とページ番号を簡潔に要約してよい。
- 検索結果が多い場合は、`match_count` と主要な先頭結果を示し、必要に応じて絞り込み語を提案する。

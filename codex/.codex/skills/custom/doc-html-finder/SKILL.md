---
name: doc-html-finder
description: Locate target passages in documents that have been converted to structured HTML, using readonly/raw/meta JSON summaries and tables of contents plus readonly/html/*/index.html page sections. Use when Codex needs to answer Japanese questions such as finding which document and PDF page contains a requested concept, requirement, rule, lesson, or passage, and return document names, page numbers, reference excerpts, and reasons.
---

# Doc HTML Finder

## 概要

`readonly/raw/meta/*.json` の概要・目次と `readonly/html/*/index.html` のページ別 HTML から、ユーザが探している文章が記載された文書と PDF ページ番号を特定する。

想定データ構造:

- `readonly/raw/meta/<文書名>.json`: `title`、`summary`、`table_of_contents` を持つメタデータ。
- `readonly/html/<文書名>/index.html`: `<section class="page" id="page-N">` で PDF ページごとに区切られた HTML。
- meta と HTML は `<文書名>` のベース名一致で対応させる。

## 基本ワークフロー

1. `readonly/raw/meta/*.json` をすべて読み、各文書の `title`、`summary`、`table_of_contents` を把握する。
2. ユーザ質問から関連語、同義語、章題候補を作る。
3. 関連しそうな文書を複数選択する。迷う場合は除外せず候補に残す。
4. 各候補文書で目次文字列を検索し、該当ページ候補を得る。
5. 候補ページと、必要に応じて前後ページを抽出して本文を確認する。
6. 最終的に目的の文章が記述されている文書と PDF ページ番号を特定する。

## スクリプト

Python は必ず `uv run python` で実行する。

### 目次からページ候補を探す

```powershell
uv run python .\.codex\skills\doc-html-finder\scripts\search_toc_pages.py ".\readonly\html\<文書名>\index.html" "安全要求"
```

入力には `index.html` か文書ディレクトリを指定できる。出力は JSON で、目次タイトル、PDF ページ番号、スコア、マッチした語を返す。

複数語を明示する場合:

```powershell
uv run python .\.codex\skills\doc-html-finder\scripts\search_toc_pages.py ".\readonly\html\<文書名>" "安全要求" --terms "合意" "セキュリティ"
```

### ページ section を抽出する

```powershell
uv run python .\.codex\skills\doc-html-finder\scripts\extract_html_pages.py ".\readonly\html\<文書名>\index.html" 34,35,36
```

入力には `index.html` か文書ディレクトリを指定できる。指定ページに対応する `<section class="page" id="page-N">...</section>` をページ順に結合して返す。

前後ページも確認する場合:

```powershell
uv run python .\.codex\skills\doc-html-finder\scripts\extract_html_pages.py ".\readonly\html\<文書名>\index.html" 34 --context 1
```

## 判断ルール

- 目次に完全一致がなくても、`summary` と目次の意味が近ければ候補文書に残す。
- 目次検索で得たページは開始ページとして扱う。節が複数ページに続く可能性があるため、本文確認では前後 1 ページ以上を見る。
- HTML の表、図キャプション、箇条書きも参照元になり得る。必要なら HTML タグを残したまま確認する。
- 本文確認時に `<img src="...">` があり、図表・スクリーンショット・画像化された表が判断に必要な場合は、`index.html` からの相対パスとしてリンク先画像も確認する。
- 抜粋は短くし、ユーザが該当箇所を追える程度にする。
- ページ番号は HTML の `id="page-N"` と `.page-label` の `PDF p.N` を PDF ページ番号として扱う。

## 最終回答形式

日本語で、標準では以下の形式で返す。

```markdown
- 文書: <文書名>
  ページ: PDF p.<ページ番号>
  参照元: <本文からの短い抜粋>
  理由: <ユーザ質問との対応関係>
```

候補が複数ある場合はすべて列挙する。見つからない場合は、確認した文書・ページ候補と、見つからないと判断した理由を簡潔に示す。

## 呼び出し例

- 「安全要求の合意形成に関する本文箇所を特定して」
- 「コーディング規約の作成について記載されている文書とページを探して」
- 「障害対策手法に関係する教訓が載っているページを参照元を明示して教えて」

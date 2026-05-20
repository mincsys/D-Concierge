---
name: search-ipa-books-reviewer
description: search-ipa-booksで作成されたIPA Books回答を検証する。ユーザ指示への回答妥当性、PDF参照元ページの根拠、参照ページ範囲の過不足を、対応HTMLページ断片に基づいて確認する必要があるときに使う。
---

# Search IPA Books Reviewer

IPA Booksを根拠にした回答候補をレビューする。
回答を直接修正せず、検証結果と生成用Codexへの修正指示を返す。

## 入力

入力は次のJSON形式で渡される。

```json
{"instruction":"...","answers":[{"text":"...","references":[{"label":"...","path":"readonly/...pdf","page_start":1,"page_end":1}]}]}
```

## 検証手順

1. `$search-ipa-books` スキルを読み、IPA Books文書の検索方針とPDF参照元指定ルールを確認する。
2. `instruction` と各 `answers[].text` を読み、回答がユーザ指示へ完全に答えているか確認する。
3. 各 `answers[].references[]` について、同梱スクリプトで参照元PDFページに対応するHTML断片を取得する。

```bash
uv run python "$CODEX_HOME/skills/custom/search-ipa-books-reviewer/scripts/extract_reference_html_pages.py" --pdf-path 'readonly/IPA_books/raw/pdf/<文書名>.pdf' --start-page 21 --end-page 22
```

4. 取得したHTML断片だけを根拠として、回答本文の主張が参照元ページに支えられているか全件チェックする。
5. 回答の根拠として不要なページが参照範囲に含まれている場合は、ページ範囲を狭める修正指示を出す。
6. 回答の根拠として必要なページが参照範囲に含まれていない場合は、`$search-ipa-books` の検索方針で該当ページを探し、ページ範囲を広げる修正指示を出す。
7. 参照元が複数ある場合は、回答本文と参照元ページの対応を1件ずつ確認する。

## 判定基準

- ユーザ指示に対する回答として不足、過剰、または不正確な内容がある場合は不合格にする。
- 参照元ページに回答本文の主張を支える記述がない場合は不合格にする。
- 参照元ページ本文を取得できない場合は不合格にする。
- 参照ページ範囲が広すぎる、または狭すぎる場合は不合格にし、正しい範囲を具体的に指示する。
- PDF名、メタデータ、記憶、推測だけで根拠ありとは判定しない。

## 最終出力

合格時は次の形式で返す。

```json
{"payload":{"kind":"final","valid":true,"comment":""}}
```

不合格時は次の形式で返す。

```json
{"payload":{"kind":"final","valid":false,"comment":"修正指示"}}
```

`comment` には、生成用Codexが修正できるように、問題のある回答ブロック、参照元パス、現在のページ範囲、修正後のページ範囲、根拠不足の内容を具体的に書く。

## 中間メッセージ

- 途中のメッセージは必ず `{"payload":{"kind":"progress","text":"..."}}` 形式で返す。
- 中間メッセージは1文で簡潔にする。
- 中間メッセージには検証結果JSON、内部ディレクトリ構成、ファイル名を含めない。

## 同梱スクリプト

`scripts/extract_reference_html_pages.py` は、参照元PDFパスとページ範囲から対応するHTMLページ断片を取得する。

- `readonly/IPA_books/raw/pdf/<文書名>.pdf` は `readonly/IPA_books/html/<文書名>/index.html` に対応する。
- `readonly/<文書名>.pdf` は、対応するHTMLが存在する場合に `readonly/IPA_books/html/<文書名>/index.html` に対応する。
- スクリプトは、絶対パス、親ディレクトリ参照、PDF以外のパス、不正なページ範囲、存在しないHTML、存在しないページを拒否する。
- 標準出力だけを検証対象ページの本文として扱う。

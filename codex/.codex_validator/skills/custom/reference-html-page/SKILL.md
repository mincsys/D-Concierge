---
name: reference-html-page
description: 検証用ワークスペースで、参照元PDFパスとページ範囲に対応するHTMLページ断片を取得する。readonly PDF参照を含む回答を検証し、対応するreadonly HTML本文を確認する必要があるときに使う。
---

# Reference HTML Page

回答が参照元PDFページの内容に支えられているか確認するときに使う。
PDFページの内容をファイル名、メタデータ、記憶から推測せず、対応するHTML断片を必ず確認する。

## ワークフロー

1. 検証対象回答の `answers[].references[].path`、`page_start`、`page_end` を取得する。
2. `readonly/` が存在するvalidator workdirで、同梱スクリプトを実行する。

```bash
python "$CODEX_HOME/skills/custom/reference-html-page/scripts/extract_reference_html_pages.py" --pdf-path 'readonly/IPA_books/raw/pdf/<document>.pdf' --start-page 21 --end-page 22
```

3. 標準出力だけを検証対象ページの本文として扱う。スクリプトは対応するHTMLの `<section>` 断片だけを出力する。
4. スクリプトが失敗した場合、その参照元ページ本文はワークスペースから確認できない。参照元を検証済みにしない。

## 注意事項

- `readonly/IPA_books/raw/pdf/<document>.pdf` は `readonly/IPA_books/raw/<document>/index.html` に対応する。
- `readonly/<document>.pdf` は、対応するHTMLが存在する場合に `readonly/IPA_books/raw/<document>/index.html` に対応する。
- スクリプトは、絶対パス、親ディレクトリ参照、PDF以外のパス、不正なページ範囲、存在しないHTML、存在しないページを拒否する。

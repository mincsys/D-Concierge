---
name: search-ipa-books
description: IPA_books配下のHTML/PDFデータソースを検索し、doc-html-finder と doc-html-keyword-search を使って、進捗JSON、最終JSON、PDF参照元付き回答を作成する。IPA Books文書を根拠に日本語質問へ回答する場合、data_source/IPA_books/raw のHTML本文確認と data_source/IPA_books/raw/pdf の実PDF参照元指定が必要な場合に使う。
---

# Search IPA Books

## 回答手順

1. `$doc-html-finder` と `$doc-html-keyword-search` を使って、ユーザの質問に関係するIPA Books文書とPDFページを探す。
2. `data_source/IPA_books/raw/<文書名>/index.html` を検索・本文確認用として扱う。
3. HTMLと同じ文書名の実PDFが `data_source/IPA_books/raw/pdf/<文書名>.pdf` に存在する前提で、参照元PDFを対応付ける。
4. 回答本文を作る前に、候補ページの内容がユーザ質問への回答を支えているか確認する。
5. 最終JSONを出力する直前に、参照元とする全ページを改めて確認し、回答を支える内容が掲載されていることを全件チェックする。
6. 最終回答は、ユーザの指示に対する完全な回答として返す。指摘事項を修正した場合も、最初の指示に対する完全な回答として返す。
7. `answers` は1つの大きな回答にせず、可能な限り複数に分け、回答本文と参照元の組を細かく対応付ける。

## 最終出力

- 最終結果のPDF参照元 `locator.path` は、必ず `data_source/` から始まる実PDFファイルへの相対パスにする。
- 最終JSONの `references[].locator.path` には、対応する `data_source/IPA_books/raw/pdf/<文書名>.pdf` を指定する。
- 絶対パス、`codex/` から始まるパス、`data_source/IPA_books/raw/.../index.html`、`data_source/IPA_books/raw/meta/...json`、`..` を含むパスは使わない。

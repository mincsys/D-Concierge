# PdfReferenceクラス設計

## 1. 文書の目的

本書は、`PdfReference` クラスの責務、不変条件、公開プロパティ、公開メソッドを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- MVPで対応する参照元種別はPDFのみである。
- Codex出力スキーマでは `start_page` / `end_page` を受け取るが、本クラスは正規化後の `page_start` / `page_end` だけを保持する。

## 3. 責務

- PDF参照元の種別、表示ラベル、共有データソース相対path、開始/終了ページを表す。
- 画面・DB向け参照元メタ情報の元になる値を提供する。
- `PdfLocator` により、共有データソース相対pathとページ範囲が成立することを保証する。
- 内部絶対パスを表示ラベルやlocatorへ混入させない。

## 4. 不変条件

- `source_type` は常に `pdf` である。
- `PdfLocator.relative_path` は共有データソースルートからのPOSIX相対pathであり、絶対path、親ディレクトリ参照、Windows区切り文字、PDF以外の拡張子を含まない。
- `PdfLocator.page_start` は1以上である。
- `PdfLocator.page_end` は `page_start` 以上である。
- 表示ラベルには内部絶対パスを含めない。
- Codex検証用に提示するpathは `readonly/<relative_path>` 形式で生成する。

## 5. 公開プロパティ

| 名前 | 型 | 役割 | 読み取り専用 |
| --- | --- | --- | --- |
| `label` | 文字列 | 画面表示用の参照元ラベルを表す。 | はい |
| `locator` | `PdfLocator` | 共有データソース相対pathと参照ページ範囲を表す。 | はい |
| `source_type` | `SourceType` | PDF参照元種別を表す。 | はい |
| `relative_path` | 文字列 | 共有データソース相対pathを返す。 | はい |
| `page_start` | 整数 | 参照範囲の開始ページを返す。 | はい |
| `page_end` | 整数 | 参照範囲の終了ページを返す。 | はい |

## 6. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `PdfReference.from_locator` | locatorのファイル名から表示ラベルを作りPDF参照元を生成する | `PdfLocator` | `PdfReference` | locatorが有効であること | 内部絶対パスを含まない表示ラベルが設定されること |
| `PdfLocator.codex_visible_path` | 検証用Codexへ提示するreadonly付きpathを生成する | なし | 文字列 | 共有データソース相対pathが有効であること | `readonly/<relative_path>` 形式のpathが返ること |

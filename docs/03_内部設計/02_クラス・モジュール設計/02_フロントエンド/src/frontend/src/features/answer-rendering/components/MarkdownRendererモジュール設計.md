# MarkdownRendererモジュール設計

## 1. 文書の目的

本書は、`MarkdownRenderer` モジュールの責務、不変条件、公開プロパティ、公開関数、および公開イベントを定義することを目的とする。

## 2. 前提

- 本書の対象は `モジュール一覧.md` で詳細設計対象とした `MarkdownRenderer` モジュールのみとする。
- Markdown構文解析は `react-markdown`、GFMは `remark-gfm`、HTML安全化は `rehype-sanitize` を利用する。
- HTMLを許可する場合でも、許可属性はsanitize schemaで制限する。

## 3. 責務

- Markdown文字列をReact要素として表示する。
- リンクは別タブで開き、`rel="noreferrer"` を付与する。
- Mermaidコードブロックを `MermaidRenderer` へ委譲する。
- 通常コードブロックをコピー可能な表示部品として描画する。
- 画像は同一オリジンかつ `/api/artifacts/` 配下のURLのみ表示する。

## 4. 不変条件

- 許可されていない画像URLはDOMへ出力しない。
- `language-mermaid` のコードブロックは通常コードブロックではなくMermaid表示へ切り替える。
- コードブロックのコピー失敗は画面全体の例外にせず、コピー状態だけを戻す。
- Markdown表示用CSSの適用対象は `markdown-body` と外部レンダラ生成DOMに限定する。

## 5. 公開プロパティ

| 名前 | 型 | 役割 | 読み取り専用 |
| --- | --- | --- | --- |
| `markdown` | 文字列 | 表示対象Markdown本文 | はい |

## 6. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `MarkdownRenderer` | Markdownを安全化して描画する | Markdown文字列 | React要素 | 入力が文字列であること | sanitize済みMarkdownが `markdown-body` 配下に表示されること |

## 7. 公開イベント

| イベント名 | 発火条件 | 通知内容 |
| --- | --- | --- |
| `コードコピー` | コードブロックのコピーボタンを選択したとき | 対象コード文字列をクリップボードへ書き込む |

# codex exec実行環境とセッション管理

## 目的

本メモは、codex execの具体的な起動例、セッション内一時領域、保存済みCodex成果物、パス検証の内部設計向け詳細を整理する。

外部IF、設定ファイルIF、論理データ設計に定義済みの契約は本メモでは繰り返さない。

## 起動例

PDF検索アプリを構成する場合の生成用codex exec起動例:

```bash
CODEX_HOME=codex/.codex \
codex exec --json --output-schema codex/output_json_schema/pdf-reference-schema.json \
  --output-last-message codex/sessions/<user-id>/<session-id>/tmp/last-message.json \
  -C codex/sessions/<user-id>/<session-id> \
  "<利用者のユーザ指示>"
```

継続指示の起動例:

```bash
CODEX_HOME=codex/.codex \
codex exec --json --output-schema codex/output_json_schema/pdf-reference-schema.json \
  --output-last-message codex/sessions/<user-id>/<session-id>/tmp/last-message.json \
  -C codex/sessions/<user-id>/<session-id> \
  resume <codex-thread-id> \
  "<利用者の継続指示>"
```

PDF検索アプリを構成する場合の検証用codex exec起動例:

```bash
CODEX_HOME=codex/.codex_validator \
codex exec --json --output-schema codex/output_json_schema/validator_schema.json \
  -C codex/sessions_validator/<user-id>/<session-id> \
  "<参照元検証依頼>"
```

継続検証の起動例:

```bash
CODEX_HOME=codex/.codex_validator \
codex exec --json --output-schema codex/output_json_schema/validator_schema.json \
  -C codex/sessions_validator/<user-id>/<session-id> \
  resume <validator-codex-thread-id> \
  "<参照元検証依頼>"
```

`resume` と `--output-schema` を併用する場合、`--json`、`--output-schema`、`--output-last-message`、`-C` は `resume` より前の `codex exec` オプションとして指定する。

## セッション内一時領域

生成用codex execからは、セッションディレクトリ直下に次のパスが見える想定とする。

```text
./readonly/
./tmp/
./artifacts/
```

検証用codex execからは、セッションディレクトリ直下に次のパスが見える想定とする。

```text
./readonly/
./tmp/
```

`tmp/` はCodexの中間作業、調査メモ、生成途中ファイルなどを保持する領域である。セッション再開時にもCodexが前回の作業状態を参照できるよう、セッションディレクトリと一緒に保持する。

`artifacts/` は生成用codex execが画像、HTML、CSV、その他の出力ファイルを一時的に置く領域である。回答Markdownから参照されるファイルは、まずこの領域に出力される。

## JSONLと最終回答の受信

`--json` は、標準出力へJSONLイベントを逐次出すために使う。バックエンドは標準出力を行単位で読み取り、実行開始、ツール実行、エラー、完了などのイベントを処理する。

`--output-schema` は、最終回答または検証結果を指定スキーマへ寄せるために使う。技術検証では、最終回答JSONは `item.completed` の `agent_message.text` に文字列として出力された。

`--output-last-message` は、最後のエージェントメッセージをファイルとして残すために併用できる。標準出力JSONLの読み取りを主経路としつつ、最終回答の取りこぼし確認やプロセス終了後の再読込に使う。

採用する使い分けは次の通りである。

- 標準出力JSONL: 実行状態、エラー、ツール実行、最後の `agent_message` を逐次受け取る。
- `--output-last-message`: 正常完了時の最後のメッセージをファイルから確認する。
- 固定検証: JSONLまたは `--output-last-message` から得た最終回答候補に対して必ず実施する。

`--output-schema` に渡すJSON Schemaは、Codex CLIが内部で利用する応答形式として受理される必要がある。技術検証では、`const` を使うプロパティにも `type` が必要だった。アプリケーション設定で指定するスキーマは、事前にcodex exec起動時の受理条件を満たすことを確認する。

## Codex成果物の保存メモ

`artifacts/` 内のファイルは、セッション継続時にcodex execが後から書き換える可能性がある。そのため、画面表示や履歴表示では `artifacts/` 内のファイルを直接参照しない。

バックエンドは回答受領時に、回答Markdownや回答JSONから参照される `artifacts/` 内のファイルを検証し、保存済みCodex成果物領域へコピーする。

回答Markdown内に含まれるセッション内 `artifacts/` への内部パスは、保存済みCodex成果物へコピーした後に `/api/artifacts/{artifact_id}` へ置換する。DBには置換後のMarkdownを回答本文として保存する。

この扱いにより、codex execがセッションディレクトリ内のファイルを更新しても、過去のチャット履歴表示は保存時点の内容を維持できる。

## パス検証

セッションディレクトリには共有データソースへの参照が含まれるため、パス検証は実体パスの解決結果を基準に行う。

検証方針は次の通りである。

- 共有データソース参照の実体は、許可済みデータソース配下に限定する。
- `tmp/` と `artifacts/` は対象セッション配下から出ていないことを検証する。
- `..` や絶対パスによるディレクトリトラバーサルを拒否する。
- Windowsではドライブ文字、大文字小文字、区切り文字、UNCパスを正規化したうえで許可範囲を判定する。
- Linuxではシンボリックリンク解決後の実体パスを基準に許可範囲を判定する。
- 共有データソース配下はCodex成果物の保存対象にしない。
- `artifacts/` から保存済みCodex成果物領域へコピーした後は、履歴表示時にセッションディレクトリ内の同名ファイルを参照しない。

## 後続設計で決めること

次の項目は、内部設計または実装設計で具体化する。

- `<user-id>/<session-id>/` 全体のサイズ上限
- セッションディレクトリの保存期間
- 古いセッションディレクトリのクリーンアップ方針
- 保存済みCodex成果物のファイル命名規則
- Codex成果物のMIMEタイプと拡張子の許可リスト
- 保存済みCodex成果物領域の容量上限とクリーンアップ方針

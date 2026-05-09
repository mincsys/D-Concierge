# codex exec JSONL出力検証

## 目的

本メモは、`codex exec --json --output-schema <schema>` の実出力を確認した技術検証の記録である。

ここでは検証条件、実測サンプル、Codex CLIの観測結果を扱う。

## 検証条件

- 実施日: 2026-05-07
- Codex CLI: `codex-cli 0.128.0`
- 生成用ホーム: `codex/.codex`
- 作業ディレクトリ: `codex/sessions/user-id-xxxxx/id-xxxxx`
- 出力スキーマ: `codex/sessions/user-id-xxxxx/id-xxxxx/tmp/verification-output-schema.json`
- 最終メッセージファイル: `codex/sessions/user-id-xxxxx/id-xxxxx/tmp/last-message-*.json`

検証用作業ディレクトリには次の要素を配置した。

```text
codex/sessions/user-id-xxxxx/id-xxxxx/
  readonly -> ../../../readonly
  tmp/
  artifacts/
```

通常実行の検証コマンド:

```bash
CODEX_HOME=codex/.codex codex exec --json --output-schema codex/sessions/user-id-xxxxx/id-xxxxx/tmp/verification-output-schema.json --output-last-message codex/sessions/user-id-xxxxx/id-xxxxx/tmp/last-message-normal.json -C codex/sessions/user-id-xxxxx/id-xxxxx "<検証用プロンプト>"
```

継続指示の検証コマンド:

```bash
CODEX_HOME=codex/.codex codex exec --json --output-schema codex/sessions/user-id-xxxxx/id-xxxxx/tmp/verification-output-schema.json --output-last-message codex/sessions/user-id-xxxxx/id-xxxxx/tmp/last-message-resume.json -C codex/sessions/user-id-xxxxx/id-xxxxx resume <codex-thread-id> "<継続指示プロンプト>"
```

## 観測結果

- `resume <codex-thread-id>` 実行時も、標準出力には `thread.started`、`turn.started`、`item.completed`、`turn.completed` がJSONLとして出力された。
- `thread.started` の `thread_id` は、指定した生成用Codex側の会話継続IDと同じ値だった。
- `--output-schema` は、`resume` より前の `codex exec` オプションとして指定すれば有効だった。
- `--output-last-message` には、通常実行時と同じく最後の `agent_message.text` と同等のJSON文字列が保存された。
- `-C` を `resume` より前に指定することで、継続指示時も指定した作業ディレクトリが使われた。
- `item.completed` のうち、`item.type` が `agent_message` のイベントでは、`item.text` にJSON文字列が入った。
- ツール実行を伴う場合は、`command_execution` の開始・完了イベントが出力された。

## 実測JSONLサンプル

resume時の最小例:

```json
{"type":"thread.started","thread_id":"019e00ec-fec8-7612-ac3e-81151b6731c3"}
```

通常完了時の `agent_message` 例:

```json
{"type":"item.completed","item":{"type":"agent_message","text":"{\"answers\":[{\"text\":\"テスト用の短い回答です。\",\"references\":[]}]}"}}
```

resume時の `agent_message` 例:

```json
{"type":"item.completed","item":{"type":"agent_message","text":"{\"answers\":[{\"text\":\"はい。resumeでも中間JSONLの継続と最終回答の受け取りを検証できます。\",\"references\":[]}]}"}}
```

`command_execution` の開始例:

```json
{"type":"item.started","item":{"type":"command_execution","command":"<コマンド>","status":"in_progress"}}
```

`command_execution` の完了例:

```json
{"type":"item.completed","item":{"type":"command_execution","command":"<コマンド>","aggregated_output":"<出力>","exit_code":0,"status":"completed"}}
```

`--output-last-message` の出力例:

```json
{"answers":[{"text":"テスト用の短い回答です。","references":[]}]}
```

## エラー時の観測結果

無効なJSON Schemaを指定した場合、標準出力JSONLには `error` と `turn.failed` が出力された。

確認したエラー分類:

```text
invalid_json_schema
```

この場合、最終回答ファイルは作成されなかった。

技術検証では、既存のPDF参照用スキーマに `const` のみで `type` がないプロパティがあり、Codex CLIの `--output-schema` では受理されなかった。

## スキーマ不適合指示時の観測結果

利用者指示でスキーマを無視するよう求めた場合でも、`--output-schema` が有効な実行では、最終的にスキーマ適合JSONが出力された。

## キャンセル時の観測結果

PTY付きでcodex exec実行中に割り込みを入れたところ、プロセスは終了コード1で終了した。割り込み時点では `turn.failed` が出力されず、`--output-last-message` のファイルも作成されなかった。

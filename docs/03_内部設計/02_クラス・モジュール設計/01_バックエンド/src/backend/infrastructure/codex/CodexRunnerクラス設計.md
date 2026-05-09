# CodexRunnerクラス設計

## 1. 文書の目的

本書は、`CodexRunner` クラスの責務、不変条件、公開メソッド、公開イベントを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- 生成用と検証用のcodex execは別設定で起動する。
- `session_id` は作業領域を決める内部IDとして扱い、Codex側resume用IDはメソッド入力で明示的に受け取る。
- `timeout_seconds` は1回のcodex execへ渡す残り秒数であり、実行全体のdeadline計算は `ExecuteChatRunUseCase` が行う。

## 3. 責務

- `codex exec --json --output-schema` を起動する。
- 継続指示または2回目以降の検証で `codex exec resume` を利用する。
- 標準出力JSONLを逐次読み取り、構造化イベントとして通知する。
- `thread.started.thread_id` を生成用または検証用Codex側resume用IDとして返す。
- `turn.completed` 時に最新の `item.completed.agent_message.text` を最終出力候補として返す。
- キャンセル要求、タイムアウト、プロセス異常終了を検知する。
- 実行中プロセスの登録有無を確認し、終了要求結果を `sent`、`already_exited`、`not_registered` に分類して返す。

## 4. 不変条件

- `resume` を使う場合、`--json`、`--output-schema`、`-C` は `resume` より前の `codex exec` オプションとして指定する。
- 生成用は `codex/.codex` と `codex/sessions/<user-id>/<session-id>` を使い、検証用は `codex/.codex_validator` と `codex/sessions_validator/<user-id>/<session-id>` を使う。
- コマンド文字列、標準出力、絶対パスは利用者向け中間メッセージへ渡さない。Codex由来の中間メッセージは `payload.kind="progress"` の `payload.text` だけから返す。`payload.kind="final"` の生成結果JSONまたは検証結果JSONは利用者向け中間メッセージへ渡さない。
- キャンセル要求後に受信したagent_messageを最終回答として採用しない。
- 終了要求後は内部固定の短いgrace timeoutだけプロセス終了を待ち、待機時間を外部設定項目として増やさない。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `run_generation` | 生成用codex execを起動する | ユーザ指示、生成用設定、作業領域、任意の生成用Codex側resume用ID、timeout_seconds、trace_id | 生成結果、JSONLイベント、生成用Codex側resume用ID | 生成用ホームと作業領域が利用可能であること<br>timeout_secondsが正の値であること | 完了時は回答候補と生成用Codex側resume用IDが返ること |
| `run_validation` | 検証用codex execを起動する | 検証指示、検証用設定、作業領域、任意の検証用Codex側resume用ID、timeout_seconds、trace_id | 検証結果、JSONLイベント、検証用Codex側resume用ID | 検証用ホームと作業領域が利用可能であること<br>timeout_secondsが正の値であること | 完了時は検証結果と検証用Codex側resume用IDが返ること |
| `cancel` | 実行中または検証中のcodex execへ終了要求を送る | チャット実行処理ID、trace_id | `sent`、`already_exited`、`not_registered` のいずれか | 対象run IDが指定されていること | 登録済みの生存プロセスには終了要求を送ること<br>登録がない場合も例外ではなく `not_registered` を返すこと |

## 6. 公開イベント

| イベント名 | 発火条件 | 通知内容 |
| --- | --- | --- |
| `jsonl_event` | codex execの標準出力から1行分のJSONLを読み取ったとき | 構造化済みJSONLイベントを通知する |
| `process_completed` | codex execが正常終了し、最終出力候補を取得したとき | 終了コード、Codex側resume用ID、最終候補を通知する |
| `process_failed` | 起動失敗、異常終了、タイムアウトが発生したとき | エラー分類と調査用要約を通知する |

# CodexRunnerクラス設計

## 1. 文書の目的

本書は、`CodexRunner` クラスの責務、不変条件、公開メソッド、公開イベントを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- 生成用と検証用のCodex実行コンテナは別設定で起動する。
- `session_id` は作業領域を決める内部IDとして扱い、Codex側resume用IDはメソッド入力で明示的に受け取る。
- `timeout_seconds` は1回のCodex実行へ渡す残り秒数であり、実行全体のdeadline計算は `ExecuteChatRunUseCase` が行う。
- Docker起動と `codex exec` コマンド組み立ては `run_codex_docker.sh` が担い、Python側は意味のある名前付き引数を渡す。

## 3. 責務

- `run_codex_docker.sh` を起動し、生成用/検証用Codex実行コンテナを実行する。
- 継続指示または2回目以降の検証で、Codex側resume用IDをshへ渡す。
- 標準出力JSONLを逐次読み取り、構造化イベントとして通知する。
- `thread.started.thread_id` を生成用または検証用Codex側resume用IDとして返す。
- `turn.completed` 時に最新の `item.completed.agent_message.text` を最終出力候補として返す。
- `type:error` または `turn.failed` を受信した場合は、Codex側エラーとして元メッセージを保持して返す。
- キャンセル要求、タイムアウト、Docker実行プロセスの異常終了を検知する。
- 実行中コンテナ名をrun IDから決定し、キャンセルとタイムアウト時に `docker stop -t 10` を送る。
- 生成用または検証用Codex実行を開始する前にrun IDとコンテナ名を同一プロセス内の実行中プロセス登録へ保存し、実行終了時に登録を解除する。
- 実行中プロセスの登録有無を確認し、終了要求結果を `sent`、`already_exited`、`not_registered` に分類して返す。

## 4. 不変条件

- `resume` を使う場合、Codex側resume用IDを `--conversation-id` としてshへ渡す。未指定時は `--conversation-id` 自体を渡さない。
- 生成用は `codex/.codex` と `codex/sessions/<user-id>/<session-id>` を使い、検証用は `codex/.codex_validator` と `codex/sessions_validator/<user-id>/<session-id>` を使う。
- 生成用コンテナ名は `d-concierge-generator-<run_id>`、検証用コンテナ名は `d-concierge-validator-<run_id>` とする。
- `CodexRunner` はcomposition rootで生成され、チャット実行本体、チャット物理削除、アカウント物理削除が同じ実行中プロセス登録を参照できるように共有される。
- 共有データソースはshへホストパスとして渡し、コンテナ内では作業ディレクトリ直下の `data_source/` として読み取り専用で提示する。
- 出力スキーマはshへ親ディレクトリとファイル名を渡し、コンテナ内では `/tmp/output_json_schema/<schema-file>` として読み取り専用で提示する。
- 検証用で生成用 `artifacts/` が存在する場合だけ、shへ `--host-artifacts` を渡す。
- コマンド文字列、標準出力、絶対パスは利用者向け中間メッセージへ渡さない。Codex由来の中間メッセージは `payload.kind="progress"` の `payload.text` だけから返す。`payload.kind="final"` の生成結果JSONまたは検証結果JSONは利用者向け中間メッセージへ渡さない。
- キャンセル要求後に受信したagent_messageを最終回答として採用しない。
- `docker rm -f` は呼ばず、コンテナ削除は `docker run --rm` と `docker stop` に任せる。
- `docker stop` 失敗はキャンセル時は `not_registered` 相当、タイムアウト時は追加エラーなしとして扱う。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `run_generation` | 生成用Codex実行コンテナを起動する | ユーザ指示、生成用設定、作業領域、共有データソース、出力スキーマ、任意の生成用Codex側resume用ID、timeout_seconds、trace_id | 生成結果、JSONLイベント、生成用Codex側resume用ID | 生成用ホームと作業領域が利用可能であること<br>timeout_secondsが正の値であること | 実行中はrun IDからコンテナ名を解決できること<br>完了時は回答候補と生成用Codex側resume用IDが返り、実行中登録が解除されること |
| `run_validation` | 検証用Codex実行コンテナを起動する | 検証指示、検証用設定、作業領域、共有データソース、出力スキーマ、任意の検証用Codex側resume用ID、任意の生成用成果物候補領域、timeout_seconds、trace_id | 検証結果、JSONLイベント、検証用Codex側resume用ID | 検証用ホームと作業領域が利用可能であること<br>timeout_secondsが正の値であること | 実行中はrun IDからコンテナ名を解決できること<br>完了時は検証結果と検証用Codex側resume用IDが返り、実行中登録が解除されること |
| `cancel` | 実行中または検証中のCodex実行コンテナへ終了要求を送る | チャット実行処理ID、trace_id | `sent`、`already_exited`、`not_registered` のいずれか | 対象run IDが指定されていること | 登録済みの実行中コンテナには `docker stop -t 10` を送ること<br>登録がない場合も例外ではなく `not_registered` を返すこと |

## 6. 公開イベント

| イベント名 | 発火条件 | 通知内容 |
| --- | --- | --- |
| `jsonl_event` | Codex実行コンテナの標準出力から1行分のJSONLを読み取ったとき | 構造化済みJSONLイベントを通知する |
| `process_completed` | Codex実行コンテナが正常終了し、最終出力候補を取得したとき | 終了コード、Codex側resume用ID、最終候補を通知する |
| `process_failed` | Codex側エラー、起動失敗、異常終了、タイムアウトが発生したとき | エラー分類と調査用要約を通知する |

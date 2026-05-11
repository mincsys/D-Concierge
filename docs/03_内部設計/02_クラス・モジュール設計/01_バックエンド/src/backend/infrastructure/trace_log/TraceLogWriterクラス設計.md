# TraceLogWriterクラス設計

## 1. 文書の目的

本書は、`TraceLogWriter` クラスの責務、不変条件、公開メソッドを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- トレースログは1異常1JSONファイルで保存する。

## 3. 責務

- API、ユースケース、infrastructureで発生した障害調査用情報をJSONへ変換する。
- trace_id、chat_id、run_id、user_id、stage、error_class、exception_type、stacktrace、retry_count、run_state、execution_deadline_at、timeout_state、cancel_state、os_name、runner_type、codex_exit_status、process_result、validation_failure_reason、validation_comment、messageを出力する。
- 開発者向け調査情報はマスクせず、巨大な文字列だけを上限長で切り詰める。

## 4. 不変条件

- 1ファイルが1件の独立したJSONオブジェクトである。
- 利用者向け画面に表示しない調査用情報だけを保存する。
- APIキー、環境変数、秘密情報、OS依存の絶対パス、生JSONL全文、コマンド出力全文は開発者向け調査情報としてそのまま保存する。
- `message`、`validation_comment`、`request_validation_errors` などは64KiB、`stacktrace` は1MiBを上限に切り詰める。
- ログ出力失敗は元処理のHTTP応答、SSEイベント、run終端状態を上書きしない。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `write` | トレースログを1件保存する | trace_id、発生段階、エラー分類、関連ID、例外情報、Codex終了情報、検証失敗情報、調査用メッセージ | なし | トレースログ保存先が設定済みであること | 日付ディレクトリ配下へ整形済みJSONファイルとして保存されること<br>同名ファイルは連番で回避されること |

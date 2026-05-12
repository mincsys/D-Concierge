# TraceLogWriterクラス設計

## 1. 文書の目的

本書は、`TraceLogWriter` クラスの責務、不変条件、公開メソッドを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- トレースログは1異常1YAMLファイルで保存する。

## 3. 責務

- API、ユースケース、infrastructureで発生した障害調査用情報をYAMLへ変換する。
- trace_id、chat_id、run_id、user_id、stage、error_type、exception_type、stacktrace、retry_count、run_state、execution_deadline_at、timeout_state、cancel_state、os_name、runner_type、codex_exit_status、process_result、validation_failure_reason、validation_comment、messageを出力する。
- `app.timezone` 基準の日時で、発生日時、日付ディレクトリ、ファイル名、保存期間削除日を決定する。
- 開発者向け調査情報はマスクせず、巨大な文字列だけを上限長で切り詰める。
- 保存期間を過ぎた日付ディレクトリを起動時に削除する。
- アプリケーション起動ごとの同日最大保存件数をメモリ上のカウンタで管理する。

## 4. 不変条件

- 1ファイルが1件の独立したYAMLドキュメントである。
- 利用者向け画面に表示しない調査用情報だけを保存する。
- APIキー、環境変数、秘密情報、OS依存の絶対パス、生JSONL全文、コマンド出力全文は開発者向け調査情報としてそのまま保存する。
- `message`、`validation_comment`、`request_validation_errors` などは64KiB、`stacktrace` は1MiBを上限に切り詰める。
- 改行を含む文字列はYAMLのブロック形式で出力する。
- 日時の取得元は呼出元から注入され、TraceLogWriterは設定ファイルを直接読まない。
- ログ出力失敗は元処理のHTTP応答、SSEイベント、run終端状態を上書きしない。
- 既存ファイル数は同日上限判定に使わず、起動後に保存できた件数だけを数える。
- 書き込み失敗時は同日保存件数を増やさない。
- 日付が変わった場合は同日保存件数を0へ戻す。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `write` | トレースログを1件保存する | trace_id、発生段階、エラー分類、関連ID、例外情報、Codex終了情報、検証失敗情報、調査用メッセージ | なし | トレースログ保存先が設定済みであること | 日付ディレクトリ配下へ整形済みYAMLファイルとして保存されること<br>同名ファイルは連番で回避されること |
| `cleanup_expired` | 保存期間を過ぎた日付ディレクトリを削除する | なし | なし | トレースログ保存先と保存期間が設定済みであること | `<trace_log.dir>/<yyyy-MM-dd>/` 形式で保存期間を過ぎたディレクトリだけが削除対象になること<br>削除失敗は呼出元へ波及しないこと |

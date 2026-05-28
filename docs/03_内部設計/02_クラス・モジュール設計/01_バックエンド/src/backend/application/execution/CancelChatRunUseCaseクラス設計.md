# CancelChatRunUseCaseクラス設計

## 1. 文書の目的

本書は、`CancelChatRunUseCase` クラスの責務、不変条件、公開メソッドを定義することを目的とする。

## 2. 前提

- 本クラスは `クラス一覧.md` で詳細設計対象としたクラスである。
- キャンセル対象は、認証済みユーザが所有する対象チャットの表示中チャット実行処理である。

## 3. 責務

- 認証済みユーザが所有するキャンセル対象実行処理の存在とキャンセル可能状態を確認する。
- 状態条件付き更新により `cancel_requested` へ遷移させる。
- 変更前状態が `accepted` の場合はcodex execプロセスへ終了要求を出さず、同一処理内で `canceled` へ遷移させる。
- 変更前状態が `running` または `validating` の場合は `CancelRequesterPort` でcodex execプロセスへ終了要求を出し、`sent`、`already_exited`、`not_registered` の結果を状態整合へ反映する。
- プロセス終了後、状態条件付き更新により `canceled` へ遷移させる。
- キャンセル失敗時に利用者向けメッセージとトレースログを保存する。
- DB更新は `TransactionManagerPort` と `CancelChatRunRepositoryPort` を通じて行い、異常系調査情報は `TraceLoggerPort` へ渡す。

## 4. 不変条件

- キャンセル要求は、対象実行処理が `accepted`、`running`、`validating` のいずれかである場合だけ受け付ける。
- `cancel_requested` になった実行処理では、後続の回答候補を採用しない。
- `canceled` では未検証回答と途中Codex成果物を保存しない。
- `accepted` の実行処理にはCodexRunner登録済みプロセスが存在しないため、`not_registered` をエラー扱いしない。
- `already_exited` または `not_registered` の場合も、DB上で回答採用前であれば `canceled` へ整合させる。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `request_cancel` | キャンセル要求を受け付ける | 認証済みユーザID、チャットID、チャット実行処理ID、trace_id | キャンセル要求中またはキャンセル済み状態と利用者向けメッセージ | 対象実行処理が認証済みユーザのチャットに紐づいて存在すること<br>対象実行処理がキャンセル可能状態であること | 変更前状態が `accepted` の場合は対象実行処理の状態が `canceled` になること<br>変更前状態が `running` または `validating` の場合は対象実行処理の状態が `cancel_requested` になり、終了要求結果が記録されること<br>利用者向けメッセージが `処理をキャンセルしています。` またはキャンセル完了メッセージになること |
| `complete_cancel` | codex exec終了後にキャンセル済みを確定する | チャット実行処理ID、`sent` / `already_exited` / `not_registered` の終了要求結果、trace_id | キャンセル済みまたはエラー状態 | 対象実行処理が `cancel_requested` であること | `sent`、`already_exited`、`not_registered` のいずれでも回答採用前なら状態が `canceled` になること<br>状態競合で回答採用済みの場合はDB上の終端状態を維持し、トレースログが保存されること |

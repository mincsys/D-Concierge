# テストコードレビュー checklist

レビュー対象: F003 アプリ設定・チャット受付・履歴再表示 テストコードレビュー round-2
レビュー日時: 2026-06-21
レビュー担当: Codex 検証担当

## 1. 仕様・設計との整合

- [x] 1.1 対象機能のテスト観点が docs の機能範囲と一致している。
  - 検証結果: 指摘なし
  - 確認根拠: F003 対象はアプリ設定取得、新規チャット開始、継続指示、履歴一覧、履歴詳細であり、単体テストは `test_chat_acceptance_use_cases.py` と `test_chat_history_use_cases.py`、結合テストは `test_chat_acceptance_history_api.py` で同範囲を扱っている。SSE、キャンセル、実行回復、Codex 実行、成果物配信、物理削除はテスト要求に含めていない。

- [x] 1.2 外部 IF の API メソッド、パス、ステータス、レスポンス形式を検証している。
  - 検証結果: 指摘なし
  - 確認根拠: `GET /api/app-config`、`POST /api/chats/start`、`POST /api/chats/{chat_id}/runs`、`GET /api/chat-histories`、`GET /api/chats/{chat_id}` の正常系と主要異常系を結合テストで確認している。round-2 追加により保護対象 API の Cookie なし `401 unauthorized`、継続指示の `400`、`404`、`409` も確認対象になっている。

- [x] 1.3 内部処理設計の主要分岐と業務ルールをテストしている。
  - 検証結果: 指摘なし
  - 確認根拠: 新規チャット開始、継続指示受付、履歴一覧、履歴詳細のユーザ分離、削除中データ除外、未完了 run 競合、dispatcher 登録失敗時の run error 化を単体テストで扱っている。round-2 で継続指示の空入力、削除中チャット、dispatcher 失敗時の異常系が追加済み。

- [x] 1.4 DB 物理設計と保存・参照対象の整合を確認している。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テスト補助 `tests/support/chat.py` は `chats`、`chat_runs`、`user_instructions`、`chat_events` など F003 で使うテーブルの seed/観測 helper を持ち、API 実行後の作成件数、本文、状態、ユーザ分離を検証している。

- [x] 1.5 後続機能や対象外責務をテストで要求していない。
  - 検証結果: 指摘なし
  - 確認根拠: F004 以降の SSE 配信、キャンセル、実行回復、Codex 実行、成果物配信、F007 物理削除は期待値に含めず、F003 の受付・永続化・履歴再表示境界に絞っている。

## 2. 単体テストの品質

- [x] 2.1 UseCase の公開契約を重複定義せず、設計上の入力 DTO/Command 境界で確認している。
  - 検証結果: 指摘なし
  - 確認根拠: テストは新規チャット開始・継続指示・履歴取得の Command/DTO と Port 契約を前提にし、実装内部の private helper や別形式の `execute` 契約を追加要求していない。

- [x] 2.2 正常系の出力と副作用を具体的に確認している。
  - 検証結果: 指摘なし
  - 確認根拠: 新規チャット開始では chat/run/instruction の生成、継続指示では既存 chat への run 追加、履歴一覧・詳細では表示順、タイトル、最終更新、イベント本文を確認している。

- [x] 2.3 入力不正・対象なし・状態不整合など主要異常系を確認している。
  - 検証結果: 指摘なし
  - 確認根拠: 新規チャットと継続指示の空入力、存在しない chat、削除中 chat、未完了 run 競合、dispatcher 失敗を単体テストで確認している。既存 issue `2026-06-21_23-00-02` の不足観点は round-2 追加で解消済み。

- [x] 2.4 異常時の副作用なし、または設計された補償動作を確認している。
  - 検証結果: 指摘なし
  - 確認根拠: 空入力・対象なし・削除中・未完了 run 競合では保存・dispatcher 呼び出しが発生しないこと、dispatcher 失敗では保存済み run が `error` 化されることを単体テストで検証している。

- [x] 2.5 Fake/Stub がテスト目的に対して過剰または曖昧でない。
  - 検証結果: 指摘なし
  - 確認根拠: `tests/support/chat.py` の fake repository、dispatcher、固定 ID/時刻は呼び出し記録と保存状態を観測できる範囲に限定され、後続実装や外部サービスの振る舞いを過剰に模倣していない。

- [x] 2.6 Port/DTO 契約テストが型・属性・責務を明確にしている。
  - 検証結果: 指摘なし
  - 確認根拠: `test_chat_port_contracts.py` は ChatRepository DTO/Port と RunExecutionDispatcher Port のプロトコル、主要 DTO の属性、呼び出し境界を確認している。

## 3. 結合テストの品質

- [x] 3.1 API から DB までの結合契約を確認している。
  - 検証結果: 指摘なし
  - 確認根拠: `test_chat_acceptance_history_api.py` は API 呼び出し後に PostgreSQL の chat/run/instruction/event 状態を観測し、REST 応答だけでなく永続化契約も確認している。

- [x] 3.2 認証・ユーザ分離・保護対象 API の契約を確認している。
  - 検証結果: 指摘なし
  - 確認根拠: ログイン済みユーザ別の履歴分離に加え、round-2 追加の Cookie なしアクセスでは `POST /api/chats/start`、`POST /api/chats/{chat_id}/runs`、`GET /api/chat-histories`、`GET /api/chats/{chat_id}` が `401 unauthorized` になることを検証している。

- [x] 3.3 未ログイン書込系 API が DB を更新しないことを確認している。
  - 検証結果: 指摘なし
  - 確認根拠: round-2 追加テストで Cookie なしの start/runs 実行後に `chats`、`chat_runs`、`user_instructions` の件数と既存 instruction 本文が変化しないことを確認している。既存 issue `2026-06-21_23-00-01` は解消済み。

- [x] 3.4 REST エラー形式が共通仕様と整合している。
  - 検証結果: 指摘なし
  - 確認根拠: 未ログインは `error.code=unauthorized`、入力不正は `validation_error` と `field_errors`、対象なしは `not_found`、削除中・未完了競合は `conflict` を期待し、FastAPI 標準 `detail` の漏えいがないことを確認している。

- [x] 3.5 継続指示 API の主要異常系を結合で確認している。
  - 検証結果: 指摘なし
  - 確認根拠: round-2 追加テストで空入力 `400`、対象なし `404`、削除中 chat `409`、DB 非更新を確認しており、既存 issue `2026-06-21_23-00-02` の結合観点も解消済み。

- [x] 3.6 Red の失敗理由が未実装範囲に由来している。
  - 検証結果: 指摘なし
  - 確認根拠: 生成役報告では unit は `backend.application.chat` / `backend.application.history` / F003 Port/DTO 未作成、integration は chat API route 未登録による `404` と FastAPI 標準 `detail` 応答が主因。収集エラー、ruff エラー、DB 接続エラー、F003 以外の既存機能破壊は報告されていない。

## 4. テストデータ・補助コード

- [x] 4.1 補助関数・fixture が意味のある型を使っている。
  - 検証結果: 指摘なし
  - 確認根拠: `tests/support/chat.py` は TypedDict payload、dataclass/固定値 helper を用い、AGENTS.md で禁止されている広すぎる `dict[str, object]`、安易な `Any`、`cast(...)` に依存した payload 表現は見当たらない。

- [x] 4.2 テストデータが仕様上の境界値や状態を表現している。
  - 検証結果: 指摘なし
  - 確認根拠: 空文字・空白、削除中状態、未完了 run、dispatcher 失敗、他ユーザ chat、存在しない chat、Cookie なしなど、F003 の境界条件を固定 ID/時刻で再現している。

- [x] 4.3 テスト間の独立性を損なう共有状態がない。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは各ケースで fake repository/dispatcher/clock/id provider を生成し、結合テストは seed helper と観測 helper でケースごとに DB 状態を作る構成になっている。

- [x] 4.4 テスト補助が実装詳細へ過度に依存していない。
  - 検証結果: 指摘なし
  - 確認根拠: API 結合テストは外部 IF と DB 契約を確認し、単体 fake は Port の呼び出し結果と保存状態を観測する。presentation 内部関数や実装クラス private メソッドを直接要求していない。

## 5. 可読性・保守性

- [x] 5.1 テスト名が観点と期待結果を具体的に表している。
  - 検証結果: 指摘なし
  - 確認根拠: `test_start_chat_api_creates_chat_run_instruction_and_event`、`test_append_chat_run_api_rejects_blank_instruction_without_db_write`、`test_chat_protected_apis_reject_missing_cookie_without_db_write` など、対象動作と副作用が名称から読み取れる。

- [x] 5.2 docstring またはコメントに「観点」「確認」が記録されている。
  - 検証結果: 指摘なし
  - 確認根拠: レビュー対象テストは docstring で観点と確認内容を日本語で記録しており、なぜそのケースが必要かを追える。

- [x] 5.3 期待値が曖昧な部分一致に偏っていない。
  - 検証結果: 指摘なし
  - 確認根拠: ステータスコード、error code、field_errors、DB 件数、保存本文、状態、ユーザ ID を具体値で確認している。必要な箇所では `detail` 非存在も明示している。

- [x] 5.4 テストが過度に脆い実装順序や内部表現へ依存していない。
  - 検証結果: 指摘なし
  - 確認根拠: 固定 ID/時刻は観測可能な契約の安定化に使われ、内部処理順序や private 構造そのものを期待値にしていない。

- [x] 5.5 不要なスキップ、xfail、TODO、暫定コメントがない。
  - 検証結果: 指摘なし
  - 確認根拠: レビュー対象の F003 テスト群に、未実装を隠す skip/xfail や後続対応を曖昧にする TODO 前提のテストは見当たらない。

## 6. ディレクトリ・境界

- [x] 6.1 テストファイルの配置が既存構成と整合している。
  - 検証結果: 指摘なし
  - 確認根拠: application 単体は `src/backend/tests/unit/application/chat/`、Port 契約は `src/backend/tests/unit/application/ports/`、API/DB 結合は `src/backend/tests/integration/`、補助は `src/backend/tests/support/` に配置されている。

- [x] 6.2 既存 F001/F002 の責務やテストを不必要に変更していない。
  - 検証結果: 指摘なし
  - 確認根拠: round-2 未ステージ差分は F003 の chat acceptance/history テストと F003 state 追記が中心で、F001/F002 の機能テスト契約を変更する内容は確認対象差分に含まれていない。

- [x] 6.3 後続実装者が Red から実装契約を読み取れる。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは application/port の必要な公開契約を示し、結合テストは route、認証、DB 変更、共通エラー形式を示しているため、F003 実装で満たすべき契約が明確。

## 7. 証跡・実行結果との整合

- [x] 7.1 生成役の ruff 結果がテストコード作成後の状態として記録されている。
  - 検証結果: 指摘なし
  - 確認根拠: 生成役 round-1 修正報告では `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/backend/tests` が `All checks passed!` と記録されている。

- [x] 7.2 Unit Red 結果が未実装起因として妥当である。
  - 検証結果: 指摘なし
  - 確認根拠: 生成役報告は `17 failed, 105 passed` で、失敗主因を F003 application/history/Port/DTO 未作成としている。既存機能破壊や収集エラーは報告されていない。

- [x] 7.3 Integration Red 結果が未実装起因として妥当である。
  - 検証結果: 指摘なし
  - 確認根拠: 生成役報告は `10 failed, 53 passed` で、失敗主因を F003 chat API route 未登録による `404 Not Found` と標準 `detail` 応答としている。DB 接続エラーは報告されていない。

- [x] 7.4 実行ログ要約とレビュー対象差分に矛盾がない。
  - 検証結果: 指摘なし
  - 確認根拠: round-2 の未ステージ差分は、生成役報告どおり `test_chat_acceptance_use_cases.py` と `test_chat_acceptance_history_api.py` の追加異常系、および F003 state 追記が対象になっている。

## 8. 指摘・修正方針

- [x] 8.1 既存 issue の解消判定を行っている。
  - 検証結果: 指摘なし
  - 確認根拠: `2026-06-21_23-00-01_F003保護対象チャットAPIの未ログイン契約が不足.md` は Cookie なし保護対象 API と DB 非更新確認の追加により解消済み。`2026-06-21_23-00-02_F003継続指示受付テストが主要異常系を網羅していない.md` は継続指示の単体/結合異常系追加により解消済み。

- [x] 8.2 新規指摘が必要なテスト不足や境界違反がない。
  - 検証結果: 指摘なし
  - 確認根拠: F003 テストコード全体をゼロベースで確認し、docs/IF/処理設計との明確な不整合、後続機能の過剰要求、型制約違反、Red 妥当性の問題は見当たらなかった。

- [x] 8.3 レビュー結果が次アクションに使える粒度で整理されている。
  - 検証結果: 指摘なし
  - 確認根拠: 既存 issue 2 件は削除可、削除禁止 issue と新規 issue はなし。F003 テストコードレビュー round-2 は完了扱い可能と判定できる。

- [x] 8.4 機能別総合テスト・正式総合テストの領域をこの段階で要求していない。
  - 検証結果: 対象外
  - 確認根拠: 現フェーズは F003 テストコードレビューであり、総合テスト仕様・evidence の作成や正式総合テスト実行は対象外。

## 9. 対象外・判断不能

- [x] 9.1 実装コード品質レビューは対象外として扱っている。
  - 検証結果: 対象外
  - 確認根拠: F003 本実装は未作成であり、現フェーズはテストコードレビュー。実装品質、coverage、静的解析の最終評価は後続フェーズで扱う。

- [x] 9.2 テスト実行・DB 接続・アプリ起動を検証役が実行していない。
  - 検証結果: 対象外
  - 確認根拠: ユーザ指示に従い、検証役は pytest、ruff、mypy、アプリ起動、DB 接続、coverage 生成を実行せず、生成役報告とファイル内容のレビューで判定した。

- [x] 9.3 state/tasklist の更新は対象外として扱っている。
  - 検証結果: 対象外
  - 確認根拠: 検証役はレビュー checklist の記録と issue 判定のみを行い、`.tmp/implement-from-docs-v2/features/F003_chat_acceptance_history/state.md` と tasklist は更新対象外とした。

- [x] 9.4 判断不能項目がある場合は理由を明示している。
  - 検証結果: 指摘なし
  - 確認根拠: 今回のレビューでは判断不能項目はない。生成役実行結果は再実行せず報告ベースで扱うが、Red 妥当性の判定に必要な情報は揃っている。

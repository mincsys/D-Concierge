# F007 チャット削除・アカウント削除・回復・トレースログ

## 機能概要

チャット削除受付・物理削除、アカウント削除受付・物理削除、起動時アカウント回復、トレースログ出力、削除中データの通常操作対象外制御を実装する。

## 関連 docs

- `docs/02_外部設計/02_業務設計/チャット削除フロー.md`
- `docs/02_外部設計/02_業務設計/アカウント管理フロー.md`
- `docs/02_外部設計/08_共通設計/ログ設計.md`
- `docs/03_内部設計/04_処理設計/チャット削除受付処理設計.md`
- `docs/03_内部設計/04_処理設計/チャット物理削除処理設計.md`
- `docs/03_内部設計/04_処理設計/アカウント削除受付処理設計.md`
- `docs/03_内部設計/04_処理設計/アカウント物理削除処理設計.md`
- `docs/03_内部設計/04_処理設計/起動時アカウント回復処理設計.md`
- `docs/03_内部設計/03_内部IF設計/ChatDeletionDispatcherIF.md`
- `docs/03_内部設計/03_内部IF設計/AccountDeletionDispatcherIF.md`
- `docs/03_内部設計/03_内部IF設計/トレースログIF.md`

## 前提機能

F001、F002、F003、F004、F006

## 現在フェーズ

機能結合完了

## ループ回数

3

## サブエージェント状態

- 対象役割: 検証役
- 起動状態: 再利用再開
- 直前フェーズ: 機能別総合テストレビュー round-1
- 最終依頼: F007 機能別総合テストレビュー round-1
- 最終応答: 完了
- 中断理由:
- 再開方針:
- 新規再起動理由:
- 引き継ぎ要約: F007 テストコードレビュー round-3 は合格。実装、単体テスト、結合テスト、coverage、静的確認は完了。結合テスト完了検証と実装品質レビュー round-2 は合格。round-1 の3 issue はすべて解消済みとして削除済み。F007 機能別総合テストレビュー round-1 は合格。正式総合テストへの持ち越しを残して機能結合完了。
- `SKILL.md` 軽読指示: 済
- 再開後の完了報告: F007 の実装、単体・結合テスト、coverage、静的確認が完了。round-1 指摘3件の修正も完了。正式/機能別総合テストは未実施。

## Red確認結果

- 静的確認:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` を実行。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check --fix ...` を実行。
  - `git diff --check` は pass。
- 単体テスト:
  - 対象単体テストで 18 failed, 14 passed。
- 結合テスト:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_deletion_recovery_trace_api.py -q` で 3 failed。
- Red 理由:
  - `backend.application.chat.delete_chat` 未実装。
  - `execute_account_deletion` / `recover_deleting_accounts` 未実装。
  - F007 用 port / DTO 契約不足。
  - `DELETE /api/chats/{chat_id}` が未実装で 405。
  - 起動時期限切れセッション削除が未実装で `login_sessions` が残存。
- Red が成立しない理由:
  - 追加した F007 対象テストは Red 成立済み。
  - 既存のアカウント削除受付は一部実装済みのため、新規 Red 対象は物理削除、起動時回復、チャット削除、削除系 port 契約に寄せている。

### テスト修正 round-1 後

- 静的確認:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` は pass。
  - `git diff --check` は pass。
- 単体テスト:
  - 対象単体テストで 18 failed, 14 passed。
- 結合テスト:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_deletion_recovery_trace_api.py -q` で 6 failed, 1 passed。
- Red 理由:
  - F007 本実装前の Red。削除中通常操作除外は既存実装で pass。
- Red が成立しない理由: なし。本実装未実施による Red はフェーズ上の想定。

## テストコード作成結果

- 単体テスト:
  - `src/backend/tests/unit/application/chat/test_chat_deletion_use_cases.py`
  - `src/backend/tests/unit/application/account/test_account_deletion_recovery_use_cases.py`
  - `src/backend/tests/unit/application/ports/test_chat_port_contracts.py`
  - `src/backend/tests/unit/application/ports/test_account_auth_port_contracts.py`
  - `src/backend/tests/unit/application/ports/test_file_delivery_port_contracts.py`
  - `src/backend/tests/unit/application/ports/test_codex_artifact_port_contracts.py`
- 結合テスト:
  - `src/backend/tests/integration/test_deletion_recovery_trace_api.py`
- 補助ファイル: なし。必要な fake / stub は追加テストファイル内に閉じている。
- 未完了事項: 本実装は依頼範囲外のため未実施。coverage は Red 確認段階のため未実施。

### テスト修正 round-1

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 対象 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-00_F007チャット物理削除テストがDTO契約外の未完了run取得に依存.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-01_F007トレースログ単体テストがTraceLogRecord契約を検証していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-02_F007起動時アカウント回復の結合テストが再登録を観測していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-04_F007削除中チャットの通常操作対象外テストが不足.md`
- 対応概要:
  - チャット物理削除単体テストから契約外の `list_unfinished_runs_for_chat_deletion()` fake を削除し、未完了 run を `ChatDeletionTarget.unfinished_run_ids` で表現するよう修正した。
  - チャット/アカウント削除・回復の trace fake を `write(TraceLogRecord)` 契約へ変更し、`event_name`、`stage`、`error_type`、`trace_id`、関連 ID、message、exception 情報を検証するようにした。
  - 起動時アカウント回復の結合テストで dispatcher fake を monkeypatch 注入し、`registered`、`already_registered`、`failed` と failed 時 trace log を観測するようにした。
  - チャット/アカウント物理削除の結合テストを追加し、実 PostgreSQL、実ファイル領域、`TraceLogWriter` 境界で正常削除とファイル境界失敗を確認対象化した。
  - 削除中チャットに対する継続指示、SSE、参照元、成果物配信の `409` 拒否テストを追加した。
- 解消したと判断する issue: 生成役判断では対象 issue 5 件を解消。
- 未解決 issue: 生成役判断ではなし。レビュー判定待ち。
- 仕様書側修正: なし。

## テストコード検証結果

### round-1

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 不合格
- 完了可否: F007 テストコード検証は完了扱い不可。修正後再レビューが必要。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/01_test-code/round-1/test-review-checklist.md`
- checklist 総項目数: 33
- checklist 処理済み項目数: 33
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 11
- checklist 対象外件数: 9
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 判断: チャット物理削除テストのDTO契約外依存、TraceLogRecord契約未検証、起動時アカウント回復のdispatcher再登録未観測、物理削除のDB/ファイル境界結合テスト不足、削除中チャット通常操作対象外テスト不足が残る。

### round-2

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 不合格
- 完了可否: F007 テストコード検証は完了扱い不可。残 issue 解消後の再レビューが必要。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/01_test-code/round-2/test-review-checklist.md`
- checklist 総項目数: 33
- checklist 処理済み項目数: 33
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 7
- checklist 対象外件数: 9
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 判断: 前回5 issue中4件は解消済み。`F007物理削除のDBファイル境界結合テストが不足` は、アカウント物理削除の失敗時DB維持・TraceLogWriter保存が結合テスト未確認のため未解消。

### round-3

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 合格
- 完了可否: F007 テストコード検証は完了扱い可。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/01_test-code/round-3/test-review-checklist.md`
- checklist 総項目数: 33
- checklist 処理済み項目数: 33
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 0
- checklist 対象外件数: 9
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 判断: 残 issue 1 件は解消済み。実Repository、実 `FileArtifactStore`、実 `TraceLogWriter` を使ったアカウント物理削除のファイル境界失敗テストが追加され、DB上のユーザ・チャット・成果物メタ維持と `account_physical_deletion_failed` trace log 保存を確認対象にしている。新規指摘なし。

## テストコードレビュー指摘

### round-1

- round-1 作成 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-00_F007チャット物理削除テストがDTO契約外の未完了run取得に依存.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-01_F007トレースログ単体テストがTraceLogRecord契約を検証していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-02_F007起動時アカウント回復の結合テストが再登録を観測していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-04_F007削除中チャットの通常操作対象外テストが不足.md`
- round-1 削除可 issue: なし
- round-1 削除禁止 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-00_F007チャット物理削除テストがDTO契約外の未完了run取得に依存.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-01_F007トレースログ単体テストがTraceLogRecord契約を検証していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-02_F007起動時アカウント回復の結合テストが再登録を観測していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-04_F007削除中チャットの通常操作対象外テストが不足.md`
- round-1 残 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-00_F007チャット物理削除テストがDTO契約外の未完了run取得に依存.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-01_F007トレースログ単体テストがTraceLogRecord契約を検証していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-02_F007起動時アカウント回復の結合テストが再登録を観測していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-04_F007削除中チャットの通常操作対象外テストが不足.md`

### round-2

- round-2 解消済み issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-00_F007チャット物理削除テストがDTO契約外の未完了run取得に依存.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-01_F007トレースログ単体テストがTraceLogRecord契約を検証していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-02_F007起動時アカウント回復の結合テストが再登録を観測していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-04_F007削除中チャットの通常操作対象外テストが不足.md`
- round-2 削除可 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-00_F007チャット物理削除テストがDTO契約外の未完了run取得に依存.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-01_F007トレースログ単体テストがTraceLogRecord契約を検証していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-02_F007起動時アカウント回復の結合テストが再登録を観測していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-04_F007削除中チャットの通常操作対象外テストが不足.md`
- round-2 検証役判定に基づき削除した issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-00_F007チャット物理削除テストがDTO契約外の未完了run取得に依存.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-01_F007トレースログ単体テストがTraceLogRecord契約を検証していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-02_F007起動時アカウント回復の結合テストが再登録を観測していない.md`
  - `.issue/implement-from-docs/2026-06-23_08-10-04_F007削除中チャットの通常操作対象外テストが不足.md`
- round-2 削除禁止 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
- round-2 残 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`

### テスト修正 round-2

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 対象 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
- 対応概要:
  - `src/backend/tests/integration/test_deletion_recovery_trace_api.py` に、アカウント物理削除の保存済み成果物ディレクトリ削除失敗時を確認する結合テストを追加した。
  - 実Repository、実 `FileArtifactStore`、実 `TraceLogWriter` を使い、DB上のユーザ・チャット・成果物メタが維持され、`account_physical_deletion_failed` のトレースログが保存されることを検証する。
- 実行結果:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/backend/tests/integration/test_deletion_recovery_trace_api.py` は pass。
  - `git diff --check` は pass。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_deletion_recovery_trace_api.py -q` は 7 failed, 1 passed。
- Red 理由: F007 本実装前の Red。追加テストも `backend.application.account.execute_account_deletion` 未実装により失敗。
- 解消したと判断する issue: 生成役判断では対象 issue 1 件を解消。
- 未解決 issue: 生成役判断ではなし。レビュー判定待ち。
- 仕様書側修正: なし。

### round-3

- round-3 解消済み issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
- round-3 削除可 issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
- round-3 検証役判定に基づき削除した issue:
  - `.issue/implement-from-docs/2026-06-23_08-10-03_F007物理削除のDBファイル境界結合テストが不足.md`
- round-3 削除禁止 issue: なし
- round-3 残 issue: なし
- round-3 作成 issue: なし
- round-3 TBC 候補 issue: なし

## テストコードレビュー checklist

- round-1: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/01_test-code/round-1/test-review-checklist.md`
- round-2: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/01_test-code/round-2/test-review-checklist.md`
- round-3: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/01_test-code/round-3/test-review-checklist.md`

## 実装・結合テスト実行結果

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 実装概要:
  - チャット削除受付、チャット物理削除、アカウント物理削除、起動時削除中アカウント回復、トレースログ出力を追加した。
  - 削除中チャットの通常操作対象外制御と成果物・参照元配信の拒否境界を追加した。
  - F007 用 port / DTO / dispatcher / repository / filesystem 境界を実装した。
- 単体テスト:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/unit --cov=src/backend --cov-branch --cov-report=term`
  - 結果: 259 passed、TOTAL 98%
- 結合テスト:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_deletion_recovery_trace_api.py -q`
  - 結果: 8 passed
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_account_management_api.py src/backend/tests/integration/test_auth_account_api.py -q`
  - 結果: 22 passed
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration --cov=src/backend --cov-branch --cov-report=term`
  - 結果: 145 passed、TOTAL 91%
- 静的確認:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/backend` は pass。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check src/backend` は pass。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src/backend` は pass。
  - `git diff --check` は pass。
- coverage 証跡:
  - `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/evidence/backend-unit-coverage.log`
  - `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/evidence/backend-integration-coverage.log`
- 残 issue: なし。
- 未完了: なし。
- 判断不能: なし。

## 結合テスト検証結果

### round-1

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 不合格
- 完了可否: 完了扱い不可。実装品質レビューの blocking 指摘 3 件の修正後、再レビューが必要。
- evidence 確認:
  - 単体: 259 passed、TOTAL 98%
  - 結合: 145 passed、TOTAL 91%
  - F007 対象結合: 8 passed
  - 静的確認: pass
- quality gate: evidence 上は単体/結合/coverage/静的確認の gate を満たしている。

### round-2

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 合格
- 完了可否: 完了扱い可。
- evidence 確認:
  - F007 関連単体: 37 passed
  - F007 対象結合: 14 passed
  - 関連アカウント結合: 22 passed
  - 全単体 coverage: 264 passed、TOTAL 98%
  - 全結合 coverage: 151 passed、TOTAL 91%
  - `ruff check`、`ruff format --check`、`mypy`、`git diff --check`: 生成役報告上 pass
- quality gate: evidence 上は単体/結合/coverage/静的確認の gate を満たしている。

## 実装品質レビュー結果

### round-1

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 不合格
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/02_integration-quality/round-1/integration-quality-review-checklist.md`
- checklist 総項目数: 94
- checklist 処理済み項目数: 94
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 17
- checklist 対象外件数: 20
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 作成 issue:
  - `.issue/implement-from-docs/2026-06-23_09-20-00_F007実アプリの削除dispatcherがNullで物理削除が起動しない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-01_F007削除中チャットの起動時再登録が実装されていない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-02_F007起動時アカウント回復のDB例外がトレースして継続されない.md`
- 削除可 issue: なし
- 削除禁止 issue:
  - `.issue/implement-from-docs/2026-06-23_09-20-00_F007実アプリの削除dispatcherがNullで物理削除が起動しない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-01_F007削除中チャットの起動時再登録が実装されていない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-02_F007起動時アカウント回復のDB例外がトレースして継続されない.md`
- TBC 候補: なし
- 修正指示:
  - 実アプリ構成で Null dispatcher ではなく DB executor 付きの chat/account deletion dispatcher を接続する。
  - 起動時に `deleting` チャットを再登録し、失敗時 trace log を保存する。
  - 起動時アカウント回復で期限切れセッション削除失敗、削除中ユーザ一覧取得失敗、dispatcher 例外を trace log に残して起動継続する。

### round-1 指摘修正

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 対象 issue:
  - `.issue/implement-from-docs/2026-06-23_09-20-00_F007実アプリの削除dispatcherがNullで物理削除が起動しない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-01_F007削除中チャットの起動時再登録が実装されていない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-02_F007起動時アカウント回復のDB例外がトレースして継続されない.md`
- 対応概要:
  - `create_app()` の実構成で chat/account deletion dispatcher を Threaded + DB executor に接続し、app state 差し替えなしで executor に到達する結合テストを追加した。
  - `RecoverDeletingChatsUseCase` を追加し、起動時に `deleting` チャットを再登録するようにした。登録失敗・例外は trace log に残し、次チャットへ進む。
  - `RecoverDeletingAccountsUseCase` で期限切れセッション削除失敗、`deleting` ユーザ一覧取得失敗、dispatcher 例外を個別捕捉し、trace log へ記録して起動処理を継続するよう修正した。
- 実行結果:
  - F007 関連単体: 37 passed
  - F007 対象結合: 14 passed
  - 関連アカウント結合: 22 passed
  - backend 単体 coverage: 264 passed、TOTAL 98%
  - backend 結合 coverage: 151 passed、TOTAL 91%
  - `ruff check`、`ruff format --check`、`mypy`、`git diff --check` は pass。
- 解消したと判断する issue: 生成役判断では対象 issue 3 件を解消。
- 未解決 issue: 生成役判断ではなし。レビュー判定待ち。
- 仕様書側修正: なし。

### round-2

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 合格
- 完了可否: 完了扱い可。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/02_integration-quality/round-2/integration-quality-review-checklist.md`
- checklist 総項目数: 94
- checklist 処理済み項目数: 94
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 0
- checklist 対象外件数: 20
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 解消済み issue:
  - `.issue/implement-from-docs/2026-06-23_09-20-00_F007実アプリの削除dispatcherがNullで物理削除が起動しない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-01_F007削除中チャットの起動時再登録が実装されていない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-02_F007起動時アカウント回復のDB例外がトレースして継続されない.md`
- 削除可 issue:
  - `.issue/implement-from-docs/2026-06-23_09-20-00_F007実アプリの削除dispatcherがNullで物理削除が起動しない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-01_F007削除中チャットの起動時再登録が実装されていない.md`
  - `.issue/implement-from-docs/2026-06-23_09-20-02_F007起動時アカウント回復のDB例外がトレースして継続されない.md`
- 削除禁止 issue: なし
- 残 issue: なし
- 新規作成 issue: なし
- TBC 候補: なし

## 結合レビュー checklist

- round-1: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/02_integration-quality/round-1/integration-quality-review-checklist.md`
- round-2: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/02_integration-quality/round-2/integration-quality-review-checklist.md`

## 機能別総合テスト実行結果

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 公式 docs 更新: なし。`docs/04_テスト/04_総合テスト/` の差分なし。
- 作業用コピー:
  - `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/system-test/`
- 更新した作業用テスト仕様:
  - `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/system-test/テスト仕様・結果/チャット削除テスト.md`
  - `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/system-test/テスト仕様・結果/アカウント管理テスト.md`
- 実行結果:
  - 合格 7 件: `ST-DELETE-008`〜`ST-DELETE-013`、`ST-ACCOUNT-014`
  - 部分確認 17 件: `ST-DELETE-001`〜`ST-DELETE-007`、`ST-DELETE-014`、`ST-DELETE-015`、`ST-ACCOUNT-012`、`ST-ACCOUNT-013`、`ST-ACCOUNT-015`〜`ST-ACCOUNT-019`、`ST-ACCOUNT-022`
  - 対象外 13 件: `ST-ACCOUNT-001`〜`ST-ACCOUNT-011`、`ST-ACCOUNT-020`、`ST-ACCOUNT-021`
- 実行コマンド:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_deletion_recovery_trace_api.py -q | tee .../F007-deletion-recovery-trace-api.txt`
  - 結果: 14 passed
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_account_management_api.py src/backend/tests/integration/test_auth_account_api.py -q | tee .../F007-account-auth-api.txt`
  - 結果: 22 passed
  - `git diff -- docs/04_テスト/04_総合テスト`
  - 結果: 差分なし
  - `git diff --check -- .tmp/.../system-test`
  - 結果: pass
- 起動プロセス:
  - backend / frontend dev server は未起動。
  - pytest の in-process ASGI 実行のみ。残存プロセスなし。
  - Playwright CLI は未実行。
- 作成 issue: なし
- 残 issue: なし

## 機能別総合テスト証跡

- `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/system-test/evidence/F007-system-test-summary.txt`
- `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/system-test/evidence/F007-deletion-recovery-trace-api.txt`
- `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/system-test/evidence/F007-account-auth-api.txt`

## 機能別総合テスト保留事項

なし

## 機能別総合テストレビュー結果

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 合格
- 完了可否: 完了扱い可。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/03_feature-system-test/round-1/feature-system-test-review-checklist.md`
- checklist 総項目数: 55
- checklist 処理済み項目数: 55
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 0
- checklist 対象外件数: 14
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- docs 非変更確認: 公式 `docs/04_テスト/04_総合テスト/` は未変更。`.tmp/.../system-test/` 側に結果・備考・証跡参照が記録されている。
- 証跡確認: `F007-system-test-summary.txt` と API 証跡の `14 passed` / `22 passed` が整合。
- 分類妥当性: 妥当。画面、複数ブラウザ、SSE再接続、実 Codex コンテナ終了要求などは正式総合テストへ持ち越し。
- 作成 issue: なし
- 削除可 issue: なし
- 削除禁止 issue: なし
- TBC 候補: なし
- 機能結合完了可否: 可

## 機能別総合テストレビュー checklist

- round-1: `.tmp/implement-from-docs-v2/features/F007_deletion_recovery_trace/review-checklists/03_feature-system-test/round-1/feature-system-test-review-checklist.md`

## 正式総合テストへの持ち越し

- Chrome上の削除確認ダイアログ操作
- チャット削除確認キャンセル
- 削除受付後の開始画面 / ログイン画面遷移
- 履歴項目三点メニュー削除
- 複数ブラウザコンテキスト競合表示
- SSE再接続時の画面メッセージ
- 実行中Codexコンテナへの終了要求を含む画面起点削除
- 削除受付失敗時の画面メッセージ
- アカウント削除確認キャンセル
- 複数ブラウザセッションのログイン画面遷移
- 実行中チャットを持つアカウント削除の画面起点確認
- 物理削除失敗からアプリ再起動後完了までの画面起点通し確認

## TBC issue

なし

## 備考

削除受付後の復帰禁止とトレースログ保存範囲を共通設計とログ設計に合わせる。

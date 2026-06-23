# F006 参照元PDF・Codex成果物配信

## 機能概要

保存済み PDF 参照元メタ情報から共有データソース内 PDF を配信し、採用済み Codex 成果物を保存済み MIME type で配信する。

## 関連 docs

- `docs/02_外部設計/06_外部インターフェース設計/画面バックエンドAPI IF.md`
- `docs/03_内部設計/04_処理設計/参照元PDF取得処理設計.md`
- `docs/03_内部設計/04_処理設計/Codex成果物配信処理設計.md`
- `docs/03_内部設計/03_内部IF設計/参照元ファイルIF.md`
- `docs/03_内部設計/03_内部IF設計/成果物ファイルIF.md`
- `docs/03_内部設計/02_クラス・モジュール設計/01_バックエンド/src/backend/application/references/GetReferenceDataUseCaseクラス設計.md`
- `docs/03_内部設計/02_クラス・モジュール設計/01_バックエンド/src/backend/infrastructure/filesystem/FileArtifactStoreクラス設計.md`

## 前提機能

F001、F002、F003、F005

## 現在フェーズ

機能結合完了

## ループ回数

0

## サブエージェント状態

- 対象役割: 検証役
- 起動状態: 再利用再開
- 直前フェーズ: 機能別総合テストレビュー round-1
- 最終依頼: F006 機能別総合テストレビュー round-1
- 最終応答: 完了
- 中断理由:
- 再開方針:
- 新規再起動理由:
- 引き継ぎ要約: F006 機能別総合テストレビュー round-1 は合格扱い可。新規 issue、残 issue、TBC 候補はなく、検証役が機能結合完了可と判定した。
- `SKILL.md` 軽読指示: 済
- 再開後の完了報告:

## Red確認結果

- 静的確認:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` は追加テスト 4 ファイルで pass。
  - `git diff --check` は pass。
- 単体テスト:
  - `env PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... -q` で 8 failed。
- 結合テスト:
  - `env PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_reference_artifact_delivery_api.py -q` で 5 failed。
- Red 理由:
  - 単体テストは `backend.application.references`、`backend.application.artifacts.get_artifact`、配信用 Port/DTO が未実装のため Red。
  - 結合テストは `GET /api/references/{reference_id}` と `GET /api/artifacts/{artifact_id}` が未登録で 404 となり Red。
- Red が成立しない理由: なし。対象はすべて Red を確認済み。

### テスト修正 round-1 後

- 静的確認:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` は pass。
  - `git diff --check` は pass。
- 単体テスト:
  - `env PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...unit... -q` で 18 failed。
- 結合テスト:
  - `env PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_reference_artifact_delivery_api.py -q` で 10 failed。
- Red 理由:
  - 単体テストは F006 UseCase、Port、DTO 未実装による Red。
  - 結合テストは F006 API ルート未登録による 404 と共通エラー形式未到達の Red。
- Red が成立しない理由: なし。追加観点も Red を確認済み。

### テスト修正 round-2 後

- 静的確認:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` は pass。
  - `git diff --check` は pass。
  - `rg -n -- \"-> object|TYPE_CHECKING|OpenedReferenceFile|OpenedArtifactFile\" ...` により `-> object` 残存なし、具体 DTO 注釈を確認。
- 単体テスト:
  - `env PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... -q` で 16 failed。
- Red 理由:
  - F006 UseCase 未実装による既定の Red。
- Red が成立しない理由: なし。対象単体テストは Red を維持。

## テストコード作成結果

- 単体テスト:
  - `src/backend/tests/unit/application/references/test_get_reference_data_use_case.py`
  - `src/backend/tests/unit/application/artifacts/test_get_artifact_use_case.py`
  - `src/backend/tests/unit/application/ports/test_file_delivery_port_contracts.py`
- 結合テスト:
  - `src/backend/tests/integration/test_reference_artifact_delivery_api.py`
- 補助ファイル: なし。必要な fake/helper は追加テストファイル内に閉じている。
- 未完了事項: 本実装は禁止事項のため未実施。coverage は Green 化後の実行対象。

### テスト修正 round-1

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 対象 issue:
  - `.issue/implement-from-docs/2026-06-23_06-10-00_F006参照元と成果物の所有者削除中境界テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-01_F006配信元ファイル欠損読込失敗のテストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-02_F006許可MIMEタイプの配信テストが画像に偏っている.md`
- 対応概要:
  - 参照元 UseCase 単体テストに、別ユーザ所有、削除中チャット、PDF実体欠損、PDF読込失敗のケースを追加した。
  - 成果物 UseCase 単体テストに、別ユーザ所有、削除中チャット、保存済みファイル欠損、読込失敗、`text/html` / `text/csv` 正常配信ケースを追加した。
  - 結合 API テストに、別ユーザ所有リソース 404、削除中チャット 409、実ファイル欠損 404、`text/html` / `text/csv` 正常配信ケースを追加した。
  - テスト内 fake/helper のみ拡張し、本実装、state、tasklist、総合テスト関連は生成役未変更。
- 解消したと判断する issue: 生成役判断では対象 issue 3 件を解消。
- 未解決 issue: 生成役判断ではなし。レビュー判定待ち。
- 仕様書側修正: なし。

### テスト修正 round-2

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 対象 issue:
  - `.issue/implement-from-docs/2026-06-23_06-40-00_F006FakeStoreの戻り値注釈がobjectでDTO契約を隠している.md`
- 対応概要:
  - `FakeReferenceStore.open_reference_file(...)` の戻り値注釈を `object` から `OpenedReferenceFile` に変更した。
  - `FakeArtifactStore.open_saved_file(...)` の戻り値注釈を `object` から `OpenedArtifactFile` に変更した。
  - 実装前 Red を保つため、DTO は `TYPE_CHECKING` 配下で型参照し、実行時 import は従来どおりメソッド内に残した。
- 解消したと判断する issue: 生成役判断では対象 issue 1 件を解消。
- 未解決 issue: 生成役判断ではなし。レビュー判定待ち。
- 仕様書側修正: なし。

## テストコード検証結果

### round-1

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 不合格
- 完了可否: F006 テストコード検証は完了扱い不可。修正後再レビューが必要。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/01_test-code/round-1/`
- checklist 総項目数: 33
- checklist 処理済み項目数: 33
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 8
- checklist 対象外件数: 7
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 判断: Red確認結果は生成役報告と state に記録済みで、追加4テストファイルの配置、docstring形式、単体/結合の役割分担は概ね妥当。ただし、所有者/削除中チャット境界、配信元ファイル欠損・読込失敗、非画像許可MIMEの正常配信テストが不足している。

## テストコードレビュー指摘

### round-1

- round-1 作成 issue:
  - `.issue/implement-from-docs/2026-06-23_06-10-00_F006参照元と成果物の所有者削除中境界テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-01_F006配信元ファイル欠損読込失敗のテストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-02_F006許可MIMEタイプの配信テストが画像に偏っている.md`
- round-1 削除可 issue: なし
- round-1 削除禁止 issue: なし
- round-1 残 issue:
  - `.issue/implement-from-docs/2026-06-23_06-10-00_F006参照元と成果物の所有者削除中境界テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-01_F006配信元ファイル欠損読込失敗のテストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-02_F006許可MIMEタイプの配信テストが画像に偏っている.md`

### round-2

- round-2 解消済み issue:
  - `.issue/implement-from-docs/2026-06-23_06-10-00_F006参照元と成果物の所有者削除中境界テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-01_F006配信元ファイル欠損読込失敗のテストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-02_F006許可MIMEタイプの配信テストが画像に偏っている.md`
- round-2 削除可 issue:
  - `.issue/implement-from-docs/2026-06-23_06-10-00_F006参照元と成果物の所有者削除中境界テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-01_F006配信元ファイル欠損読込失敗のテストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-02_F006許可MIMEタイプの配信テストが画像に偏っている.md`
- round-2 検証役判定に基づき削除した issue:
  - `.issue/implement-from-docs/2026-06-23_06-10-00_F006参照元と成果物の所有者削除中境界テストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-01_F006配信元ファイル欠損読込失敗のテストが不足.md`
  - `.issue/implement-from-docs/2026-06-23_06-10-02_F006許可MIMEタイプの配信テストが画像に偏っている.md`
- round-2 作成 issue:
  - `.issue/implement-from-docs/2026-06-23_06-40-00_F006FakeStoreの戻り値注釈がobjectでDTO契約を隠している.md`
- round-2 削除禁止 issue:
  - `.issue/implement-from-docs/2026-06-23_06-40-00_F006FakeStoreの戻り値注釈がobjectでDTO契約を隠している.md`
- round-2 残 issue:
  - `.issue/implement-from-docs/2026-06-23_06-40-00_F006FakeStoreの戻り値注釈がobjectでDTO契約を隠している.md`

### round-3

- round-3 解消済み issue:
  - `.issue/implement-from-docs/2026-06-23_06-40-00_F006FakeStoreの戻り値注釈がobjectでDTO契約を隠している.md`
- round-3 削除可 issue:
  - `.issue/implement-from-docs/2026-06-23_06-40-00_F006FakeStoreの戻り値注釈がobjectでDTO契約を隠している.md`
- round-3 検証役判定に基づき削除した issue:
  - `.issue/implement-from-docs/2026-06-23_06-40-00_F006FakeStoreの戻り値注釈がobjectでDTO契約を隠している.md`
- round-3 削除禁止 issue: なし
- round-3 残 issue: なし
- round-3 作成 issue: なし
- round-3 TBC 候補 issue: なし

## テストコードレビュー checklist

- round-1: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/01_test-code/round-1/`
- round-2: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/01_test-code/round-2/`
- round-3: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/01_test-code/round-3/`

## 結合テスト検証結果

生成役による実装・テスト実行は完了。検証役レビューは未実施。

- 静的確認:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/backend` は pass。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check src/backend` は pass。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src/backend` は pass。
  - `git diff --check` は pass。
  - `git diff -- docs/04_テスト/04_総合テスト` は空。
- 単体テスト:
  - F006対象は 18 passed。
  - 全単体+coverage は `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/unit --cov=src/backend --cov-branch --cov-report=json:/tmp/backend-unit-coverage.json --cov-report= -q` で 240 passed。
  - branch coverage: 95.97%。
  - coverage 証跡: `docs/04_テスト/02_単体テスト/evidence/backend-unit-coverage.txt`
- 結合テスト:
  - F006対象は 10 passed。
  - 全結合+coverage は `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration --cov=src/backend --cov-branch --cov-report=json:/tmp/backend-integration-coverage.json --cov-report= -q` で 136 passed。
  - branch coverage: 81.55%。
  - coverage 証跡: `docs/04_テスト/03_結合テスト/evidence/backend-integration-evidence.txt`
  - `docker compose -f infra/compose.yml up -d postgres-test` は `d-concierge-postgres-test Running`。
- 実装範囲:
  - F006 application: `application/references/get_reference_data.py`, `application/artifacts/get_artifact.py`
  - F006 ports: `application/ports/database/interface.py`, `application/ports/filesystem/dto.py`, `application/ports/filesystem/interface.py`
  - F006 infrastructure: `infrastructure/filesystem/reference_store.py`, `infrastructure/filesystem/artifact_store.py`, `infrastructure/database/repositories/chat.py`
  - F006 presentation: `presentation/rest/delivery.py`
  - 既存連携調整: `app/router/registration.py`
- 未完了事項: 生成役報告上なし。総合テストは今回の禁止範囲のため未実行。

### round-1 修正後

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 対象 issue:
  - `.issue/implement-from-docs/2026-06-23_07-05-00_F006成果物MIMEと拡張子の不一致を配信前に拒否していない.md`
  - `.issue/implement-from-docs/2026-06-23_07-05-01_F006保存済み成果物欠損がデータ不整合として記録されない.md`
- 対応概要:
  - `GetArtifactUseCase` で `storage_path` 拡張子と保存済み `mime_type` の対応を検証し、不一致時はファイルを開かず `FORBIDDEN` にした。
  - `FileArtifactStore.open_saved_file` の保存済み成果物欠損を `NOT_FOUND` のまま `trace=True` にし、HTTP 404 を維持しつつ trace log 記録対象にした。
  - 単体テストに MIME/拡張子不一致ケースと欠損 trace 期待を追加・更新した。
  - 結合テストに MIME/拡張子不一致 403 ケースと、欠損時 trace log 記録確認を追加した。
  - coverage evidence を更新した。
- 実行結果:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/unit/application/artifacts/test_get_artifact_use_case.py -q` は Red 1 failed 後、Green 10 passed。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest src/backend/tests/integration/test_reference_artifact_delivery_api.py -q` は Red 2 failed 後、Green 11 passed。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/backend` は pass。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check src/backend` は pass。
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run mypy src/backend` は pass。
  - `docker compose -f infra/compose.yml up -d postgres-test` は running。
  - 全単体+coverage は 241 passed、branch coverage 95.99%。
  - 全結合+coverage は 137 passed、branch coverage 81.62%。
  - `git diff --check` は pass。
- 解消したと判断する issue: 生成役判断では対象 issue 2 件を解消。
- 未解決 issue: 生成役判断ではなし。レビュー判定待ち。
- 仕様書側修正: なし。設計書どおりの実装修正で対応。

## 実装品質レビュー結果

### round-1

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 不合格
- 完了可否: F006 結合検証フェーズは完了扱い不可。修正後再レビューが必要。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/02_integration-quality/round-1/`
- checklist 総項目数: 94
- checklist 処理済み項目数: 94
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 17
- checklist 対象外件数: 20
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 判断: 単体240 passed、結合136 passed、単体branch 95.97%、結合branch 81.55%、静的テストpass、evidence形式は確認済み。一方、成果物配信で `storage_path` 拡張子と保存MIMEの不一致を拒否しておらず、保存済み成果物ファイル欠損時も設計上の「データ不整合として記録」が行われない。

## 結合レビュー指摘

### round-1

- round-1 作成 issue:
  - `.issue/implement-from-docs/2026-06-23_07-05-00_F006成果物MIMEと拡張子の不一致を配信前に拒否していない.md`
  - `.issue/implement-from-docs/2026-06-23_07-05-01_F006保存済み成果物欠損がデータ不整合として記録されない.md`
- round-1 削除可 issue: なし
- round-1 削除禁止 issue:
  - `.issue/implement-from-docs/2026-06-23_07-05-00_F006成果物MIMEと拡張子の不一致を配信前に拒否していない.md`
  - `.issue/implement-from-docs/2026-06-23_07-05-01_F006保存済み成果物欠損がデータ不整合として記録されない.md`
- round-1 残 issue:
  - `.issue/implement-from-docs/2026-06-23_07-05-00_F006成果物MIMEと拡張子の不一致を配信前に拒否していない.md`
  - `.issue/implement-from-docs/2026-06-23_07-05-01_F006保存済み成果物欠損がデータ不整合として記録されない.md`

### round-2

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 合格
- 完了可否: F006 結合検証フェーズは完了扱い可。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/02_integration-quality/round-2/`
- checklist 総項目数: 94
- checklist 処理済み項目数: 94
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 0
- checklist 対象外件数: 24
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- issue 解消判定一覧:
  - `.issue/implement-from-docs/2026-06-23_07-05-00_F006成果物MIMEと拡張子の不一致を配信前に拒否していない.md`: 解消済み
  - `.issue/implement-from-docs/2026-06-23_07-05-01_F006保存済み成果物欠損がデータ不整合として記録されない.md`: 解消済み
- round-2 削除可 issue:
  - `.issue/implement-from-docs/2026-06-23_07-05-00_F006成果物MIMEと拡張子の不一致を配信前に拒否していない.md`
  - `.issue/implement-from-docs/2026-06-23_07-05-01_F006保存済み成果物欠損がデータ不整合として記録されない.md`
- round-2 検証役判定に基づき削除した issue:
  - `.issue/implement-from-docs/2026-06-23_07-05-00_F006成果物MIMEと拡張子の不一致を配信前に拒否していない.md`
  - `.issue/implement-from-docs/2026-06-23_07-05-01_F006保存済み成果物欠損がデータ不整合として記録されない.md`
- round-2 削除禁止 issue: なし
- round-2 残 issue: なし
- round-2 作成 issue: なし
- round-2 TBC 候補 issue: なし

## 結合レビュー checklist

- round-1: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/02_integration-quality/round-1/`
- round-2: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/02_integration-quality/round-2/`

## 機能別総合テスト実行結果

- 生成役: `019eeee6-b7b0-70e0-9fba-6990fbcbc5f5`
- 実行した機能別総合テスト:
  - F006 参照元PDF・Codex成果物配信
  - 対象ケース: `ST-CHAT-009/010/020/021/022`, `ST-HISTORY-006/007/011/012`, `ST-DELETE-008/009`
  - 実行確認: `src/backend/tests/integration/test_reference_artifact_delivery_api.py` による API/DB/ファイル境界確認 11 passed。
- コピー元: `docs/04_テスト/04_総合テスト/`
- コピー先: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/system-test/`
- 更新した `.tmp` 側 `テスト仕様・結果`:
  - `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/system-test/テスト仕様・結果/チャット実行テスト.md`
  - `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/system-test/テスト仕様・結果/履歴再表示テスト.md`
  - `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/system-test/テスト仕様・結果/チャット削除テスト.md`
- 分類別件数:
  - 合格: 0
  - 不合格: 0
  - 部分確認: 8
  - 後続機能待ち: 2
  - 環境・承認待ち: 0
  - 対象外: 1
- Playwright CLI 実行結果:
  - 未実行。F006 機能別では API/DB/ファイル配信境界を確認し、Chrome上のPDF描画、回答内成果物表示、画面エラー表示は正式総合テストへの再確認候補として記録。
- 承認付きコマンド実行結果: なし。通常コマンドのみ実行。
- 手動確認結果:
  - `GET /api/references/{reference_id}` のPDF配信、欠損、traversal、別ユーザ、未ログイン、削除中境界を確認。
  - `GET /api/artifacts/{artifact_id}` のSVG/HTML/CSV保存済みMIME配信、欠損、許可外MIME、MIME/拡張子不一致、別ユーザ、未ログイン、削除中境界を確認。
  - `git diff -- docs/04_テスト/04_総合テスト` は空。
- 保留事項と理由:
  - 参照元ビューアのChrome上PDF描画、閉じる操作、画面エラー表示は正式総合テストで再確認。
  - 回答Markdown内の成果物表示と成果物取得失敗時のUI表示は正式総合テストで再確認。
  - チャット削除操作後の参照元/成果物URL無効化は後続の削除機能と正式総合テストで再確認。
- 正式総合テストへの持ち越し候補:
  - `ST-CHAT-009`, `ST-CHAT-010`, `ST-CHAT-020`, `ST-CHAT-021`, `ST-CHAT-022`
  - `ST-HISTORY-006`, `ST-HISTORY-007`, `ST-HISTORY-011`, `ST-HISTORY-012`
  - `ST-DELETE-008`, `ST-DELETE-009`
- 未完了事項:
  - F006機能別で実施可能な API/DB/ファイル配信境界確認と `.tmp` 側記録は完了。

## 機能別総合テスト証跡

- `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/system-test/evidence/F006-reference-artifact-delivery-api.txt`
- `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/system-test/evidence/F006-system-test-summary.txt`

## 機能別総合テスト保留事項

- 参照元ビューアのChrome上PDF描画、閉じる操作、画面エラー表示は正式総合テストで再確認する。
- 回答Markdown内の成果物表示と成果物取得失敗時のUI表示は正式総合テストで再確認する。
- チャット削除操作後の参照元/成果物URL無効化は後続の削除機能と正式総合テストで再確認する。

## 機能別総合テストレビュー結果

- 検証役: `019eeff6-8ef6-72c1-b7e2-21231ec25af0`
- 結果: 合格
- 完了可否: 機能結合完了可。
- checklist 保存先: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/03_feature-system-test/round-1/`
- checklist 総項目数: 55
- checklist 処理済み項目数: 55
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 0
- checklist 対象外件数: 20
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし
- 機能別総合テスト合否: 合格扱い可。不合格0、未分類0で、部分確認8、後続機能待ち2、対象外1の分類理由と正式総合テストへの持ち越しが明確。
- docs 非変更確認: `git diff -- docs/04_テスト/04_総合テスト` は空。正本 docs は未変更。
- 証跡確認結果:
  - `F006-system-test-summary.txt` と `F006-reference-artifact-delivery-api.txt` を確認。
  - API/DB/ファイル境界は 11 passed。
  - 対象ケース、分類、正式再確認候補を追跡可能。
- 分類妥当性: 妥当。F006範囲の配信API境界は部分確認、Chrome上のPDF描画・回答内成果物表示・画面エラー表示は正式総合テスト持ち越し、削除後URL無効化は後続機能待ちとして整理されている。
- 承認付き実行確認: 環境・承認待ち0。Playwright未実行は承認不足ではなく、F006機能別ではAPI/DB/ファイル配信境界確認に絞ったためで、画面確認は正式総合テストへ持ち越し済み。
- 正式総合テストへの持ち越し:
  - ST-CHAT-009, ST-CHAT-010, ST-CHAT-020, ST-CHAT-021, ST-CHAT-022
  - ST-HISTORY-006, ST-HISTORY-007, ST-HISTORY-011, ST-HISTORY-012
  - ST-DELETE-008, ST-DELETE-009
- 作成した issue: なし
- 削除可 issue: なし
- 削除禁止 issue: なし
- 残 issue: なし

## 機能別総合テストレビュー checklist

- round-1: `.tmp/implement-from-docs-v2/features/F006_reference_artifact_delivery/review-checklists/03_feature-system-test/round-1/`

## 正式総合テストへの持ち越し

- ST-CHAT-009
- ST-CHAT-010
- ST-CHAT-020
- ST-CHAT-021
- ST-CHAT-022
- ST-HISTORY-006
- ST-HISTORY-007
- ST-HISTORY-011
- ST-HISTORY-012
- ST-DELETE-008
- ST-DELETE-009

## TBC issue

なし

## 備考

PDF 以外の参照元種別は本システムの対象外とする。

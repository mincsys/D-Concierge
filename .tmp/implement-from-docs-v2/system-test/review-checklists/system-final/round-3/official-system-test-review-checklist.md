# 正式総合テスト完了レビュー / 最終実装品質チェック round-3 checklist

- 検証フェーズ: 正式総合テスト完了レビュー / 最終実装品質チェック round-3
- 対象: F001〜F007 全体、公式総合テスト仕様・結果、公式 evidence、frontend 設定操作修正、F007 cancel 関連、最終実装品質
- 保存先: `.tmp/implement-from-docs-v2/system-test/review-checklists/system-final/round-3/official-system-test-review-checklist.md`
- 実施制約: テスト実行、静的解析実行、Playwright実行、coverage実行、git操作、CodeGraph、成果物修正、実装修正、docs修正、サブエージェント起動は禁止。許可された読み取り専用コマンドと checklist 作成のみ実施。
- 対象 issue:
  - `.issue/implement-from-docs/2026-06-23_10-30-01_正式総合テストが全件合格に達していない.md`

## 集計

- 総項目数: 32
- 処理済み項目数: 32
- 未処理項目数: 0
- 指摘あり件数: 2
- 対象外件数: 1
- 判断不能件数: 0
- 根拠なし `- [x]`: なし

## checklist

- [x] 公式総合テスト仕様の全ケース数と分類数を確認した。
  - 判定: 確認済み。
  - 確認根拠: `rg -c "\| ST-" docs/04_テスト/04_総合テスト/テスト仕様・結果` は 101 件、`rg -c "\| 合格 \|"` は 100 件、`rg -c "\| 部分確認 \|"` は該当なし、`rg -c "\| 保留 \|"` は 1 件を示した。`docs/04_テスト/04_総合テスト/evidence/OFFICIAL-playwright-screen-summary.txt:9-11` と `docs/04_テスト/04_総合テスト/evidence/OFFICIAL-system-test-round2-coverage.txt:14-16` も同じ分類を記録している。

- [x] 総合テスト方針の完了条件と現状分類を照合した。
  - 判定: 指摘あり。
  - 確認根拠: `docs/04_テスト/04_総合テスト/総合テスト方針.md:144-147` は全ケース実施済み、全ケース合格、未解決重大/中程度不具合なし、不合格/保留ケースの原因対応後再テストを完了条件としている。現状は合格 100 件、保留 1 件であり全件合格ではない。
  - 指摘: 既存 issue `.issue/implement-from-docs/2026-06-23_10-30-01_正式総合テストが全件合格に達していない.md` に継続記録済み。新規 issue は作成しない。

- [x] 残保留ケースを特定した。
  - 判定: 確認済み。
  - 確認根拠: `docs/04_テスト/04_総合テスト/テスト仕様・結果/チャット実行テスト.md:53` は `ST-CHAT-025 Codex Docker実行スモーク` のみを `保留` とし、Codex CLI が認証トークン失効により 401 の JSONL error を返したため、有効な Codex 認証または `CODEX_API_KEY` が必要と記録している。

- [x] ST-CHAT-025 の保留理由が環境認証前提か実装不備かを確認した。
  - 判定: 確認済み。
  - 確認根拠: `docs/04_テスト/04_総合テスト/evidence/OFFICIAL-codex-docker-smoke.jsonl` は `Your access token could not be refreshed because your refresh token was already used` の `type:error` と `turn.failed` を記録している。`docs/04_テスト/04_総合テスト/evidence/OFFICIAL-system-test-round2-coverage.txt:8-10` と `:29-31` は run script 起動、JSONL error、対象コンテナ残存なし、起因は環境認証前提でありアプリ実装不備ではないと記録している。

- [x] ST-CHAT-025 を TBC にすべきかを判定した。
  - 判定: 確認済み。
  - 確認根拠: `ST-CHAT-025` は実装修正ループで解消すべき未特定不具合ではなく、有効な Codex 認証または `CODEX_API_KEY` という実施環境前提待ちである。TBC として設計/実装上の確認事項へ退避するより、正式総合テストの環境認証待ち保留として最終報告へ明記するのが妥当。

- [x] ST-CHAT-025 の保留が正式総合テスト合否に与える影響を判定した。
  - 判定: 指摘あり。
  - 確認根拠: 総合テスト方針の完了条件は全件合格であり、環境認証待ちであっても `保留` が 1 件残るため正式総合テストは完了合格ではない。
  - 指摘: 既存 issue `.issue/implement-from-docs/2026-06-23_10-30-01_正式総合テストが全件合格に達していない.md` を削除禁止として残す。

- [x] frontend の設定操作中 401 遷移修正を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/frontend/src/app/App.tsx:29-33` は `handleUnauthorized` で設定ダイアログを閉じ、current user を null にし、`/login` へ replace 遷移する。`src/frontend/src/features/settings/components/SettingsDialog.tsx:200-205` は `isUnauthorizedAccountError` を検知して `onUnauthorized` を呼ぶ。

- [x] frontend のログアウト/アカウント削除失敗表示修正を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/frontend/src/features/settings/components/SettingsDialog.tsx:116-137` は logout/delete 失敗時に未捕捉例外へせず `setMessage(readAccountMessage(error))` へ流し、`src/frontend/src/features/settings/components/ConfirmActionDialog.tsx:38-40` は確認ダイアログ内に message を危険色で表示する。

- [x] frontend 修正が外部設計と整合しているか確認した。
  - 判定: 確認済み。
  - 確認根拠: `docs/02_外部設計/02_業務設計/アカウント管理フロー.md:5` の異常時扱いは、未ログインまたはセッション切れでログイン画面表示、アカウント削除受付失敗で削除できないことを表示して通常利用可能状態維持と定義する。`docs/02_外部設計/08_共通設計/エラーメッセージ設計.md` はログアウト、ユーザ名変更、パスワード変更、アカウント削除の失敗時メッセージを設定ダイアログに表示すると定義している。

- [x] frontend integration test の追加観点を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/frontend/tests/integration/account-flow.test.tsx:238-279` はユーザ名、パスワード、ログアウト、アカウント削除の失敗表示と状態維持を検証する。`src/frontend/tests/integration/account-flow.test.tsx:281-294` は設定操作中 401 でログイン画面へ遷移することを検証する。

- [x] frontend integration evidence を確認した。
  - 判定: 確認済み。
  - 確認根拠: `docs/04_テスト/04_総合テスト/evidence/OFFICIAL-frontend-integration.txt` は Vitest integration 2 files / 19 tests passed を記録している。実行はしていない。

- [x] backend integration evidence を確認した。
  - 判定: 確認済み。
  - 確認根拠: `docs/04_テスト/04_総合テスト/evidence/OFFICIAL-backend-integration.txt` は 153 passed を記録している。実行はしていない。

- [x] round-2 追加確認サマリと仕様再分類の整合を確認した。
  - 判定: 確認済み。
  - 確認根拠: `docs/04_テスト/04_総合テスト/evidence/OFFICIAL-system-test-round2-coverage.txt:18-27` は `ST-AUTH-014`、`ST-ACCOUNT-005/010/016/021`、`ST-CHAT-013〜019/023〜024` の追加確認観点を記録し、各テスト仕様・結果ファイルでも該当ケースが `合格` へ更新されている。

- [x] F007 cancel 境界の設計契約を確認した。
  - 判定: 確認済み。
  - 確認根拠: `docs/03_内部設計/03_内部IF設計/Codex実行IF.md` は物理削除処理では共有 `CodexRunner` のキャンセル結果を `CancelRequesterPort` の結果として扱うと定義している。`docs/03_内部設計/04_処理設計/チャット物理削除処理設計.md` と `アカウント物理削除処理設計.md` は未完了runへの終了要求を `CancelRequesterPort` で行い、未完了runが残る間は削除を延期すると定義している。

- [x] F007 cancel 境界の app factory 注入を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/backend/app/factory.py:111-117` は共有 `codex_runner` から `CodexRunCancelRequester` を生成し、`src/backend/app/factory.py:127-138` はこれをチャット削除 dispatcher とアカウント削除 dispatcher へ渡す。`src/backend/app/factory.py:181-196` と `:222-237` は executor へ `cancel_requester` を注入している。

- [x] F007 cancel requester 実装を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/backend/infrastructure/runtime/codex_run_cancel_requester.py:22-29` は `CodexRunner.cancel(run_id, trace_id).status` を物理削除用の文字列 status として返す。

- [x] F007 チャット物理削除 use case の未完了run処理を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/backend/application/chat/delete_chat.py:186-192` は未完了runがある場合、各 run に `self._cancel_requester.cancel(run_id, trace_id)` を呼び、作業領域削除、成果物削除、DB削除へ進まず return する。

- [x] F007 アカウント物理削除 use case の未完了run処理を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/backend/application/account/execute_account_deletion.py:80-86` は未完了runがある場合、各 run に `self._cancel_requester.cancel(run_id, trace_id)` を呼び、ユーザ作業領域削除、保存済み成果物削除、DB削除へ進まず return する。

- [x] F007 cancel 関連の結合テスト観点を確認した。
  - 判定: 確認済み。
  - 確認根拠: `src/backend/tests/integration/test_deletion_recovery_trace_api.py:790-836` は実アプリ用チャット物理削除executorが running run に注入済みキャンセル境界を呼ぶことを検証し、`:994-1049` は実アプリ用アカウント物理削除executorが running run に注入済みキャンセル境界を呼び、DB削除へ進まないことを検証している。

- [x] F007 の公式総合テスト結果を確認した。
  - 判定: 確認済み。
  - 確認根拠: `docs/04_テスト/04_総合テスト/テスト仕様・結果/チャット削除テスト.md:33` の `ST-DELETE-004` と `docs/04_テスト/04_総合テスト/テスト仕様・結果/アカウント管理テスト.md:41` の `ST-ACCOUNT-015` は `合格` で、backend integration により注入済みキャンセル境界呼び出しを確認したと記録している。

- [x] 旧 no-op cancel requester の残存を確認した。
  - 判定: 確認済み。
  - 確認根拠: `rg -n "NoopRunCancelRequester|_NoopRunCancelRequester" src docs .issue/implement-from-docs` では旧 `_NoopRunCancelRequester` の実装残存を確認していない。テスト内の `NoopCancelRequester` は呼び出し記録用 Fake であり、実アプリ wiring ではない。

- [x] 公式 evidence から古い failed locator 詳細が再混入していないか確認した。
  - 判定: 確認済み。
  - 確認根拠: 公式 evidence の主要サマリ、backend/frontend integration、Codex smoke、Playwright screen summary を確認し、round-1 で問題になった selector 調整前の failed locator 詳細を正式な合否根拠として残している記述は確認していない。

- [x] 未ステージ差分確認結果を整理した。
  - 判定: 確認済み。
  - 確認根拠: ユーザ引き継ぎの管理側確認では「最新修正は staging 済み」「未ステージ差分なし」とされている。検証役は git 操作禁止のため、独自の git 差分確認は実施していない。

- [x] pycache / サーバ待受の管理側確認結果を整理した。
  - 判定: 確認済み。
  - 確認根拠: ユーザ引き継ぎの管理側確認では `find src/backend -type d -name __pycache__ ...` は削除済み、`:8000` と `:5173` の待受なしとされている。検証役は許可範囲外の確認コマンドを実施していない。

- [x] 残 issue の解消判定を行った。
  - 判定: 未解消。
  - 確認根拠: `.issue/implement-from-docs/2026-06-23_10-30-01_正式総合テストが全件合格に達していない.md` は現状の合格 100 件 / 保留 1 件を根拠に、正式総合テスト完了レビューとしては不合格であり、アプリ完成扱いにできないと記録している。現状の仕様/evidence も同じ状態である。

- [x] 残 issue を TBC 候補として扱うべきか判定した。
  - 判定: TBC候補ではない。
  - 確認根拠: 残理由は実装修正不能な環境認証前提待ちであり、実装/設計の未確定論点として TBC 化するより、正式総合テストの保留ケースとして残 issue と最終報告へ明記するのが妥当。ただし全件合格ではないため issue は削除禁止。

- [x] 新規 issue 作成要否を確認した。
  - 判定: 不要。
  - 確認根拠: round-3 で新たな実装品質問題、docs/evidence 乖離、frontend 修正不備は確認していない。残る指摘は既存 issue 1 件で表現済み。

- [x] アプリ完成可否を判定した。
  - 判定: 不可。
  - 確認根拠: 正式総合テスト完了条件が全件合格である一方、`ST-CHAT-025` が保留で残り、既存 High issue が未解消のため、検証役としてアプリ完成扱いにはできない。

- [x] 最終報告可否を判定した。
  - 判定: 条件付きで可能。
  - 確認根拠: 最終報告は可能だが、完成報告ではなく、`ST-CHAT-025` の環境認証待ち保留、正式総合テスト未完了、アプリ完成不可、再実施条件を明記する必要がある。

- [x] 完了不可機能と保留総合テストを整理した。
  - 判定: 確認済み。
  - 確認根拠: 完了不可機能は `ST-CHAT-025 Codex Docker実行スモーク` に対応する実 Codex 認証済み Docker 実行スモークのみ。保留総合テストは `ST-CHAT-025` 1 件のみ。

- [x] レビュー制約の遵守を確認した。
  - 判定: 確認済み。
  - 確認根拠: テスト、静的解析、Playwright、coverage、git、CodeGraph、実装/docs修正、サブエージェント起動は実施していない。読み取り専用コマンドと checklist 作成のみ実施した。

- [x] レビュー対象外事項を整理した。
  - 判定: 対象外。
  - 確認根拠: 実行系コマンド禁止のため、生成役が報告した Red/Green/typecheck/lint/unit/integration/backend integration の再実行、ST-CHAT-025 の再実行、git 上の staging/unstaged 状態の直接確認は対象外とした。

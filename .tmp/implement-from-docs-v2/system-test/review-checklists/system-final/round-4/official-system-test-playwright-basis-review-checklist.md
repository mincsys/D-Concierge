# 正式総合テスト Playwright 実機確認基準レビュー checklist round-4

- 検証フェーズ: 正式総合テスト完了レビュー / Playwright 実機確認基準 round-4
- 対象: `docs/04_テスト/04_総合テスト/総合テスト方針.md`、`テスト仕様・結果/*.md`、`evidence/`、`.tmp/implement-from-docs-v2/system-test/state.md`、既存 issue 2 件
- 保存先: `.tmp/implement-from-docs-v2/system-test/review-checklists/system-final/round-4/official-system-test-playwright-basis-review-checklist.md`
- 実施制約: テスト実行、Playwright 実行、git 操作、CodeGraph、成果物修正、issue 作成は実施しない。許可された読み取り専用コマンドと checklist 作成のみ実施。

## 集計

- 総項目数: 21
- 処理済み項目数: 21
- 未処理項目数: 0
- 指摘あり件数: 10
- 対象外件数: 1
- 判断不能件数: 0
- 根拠なし `- [x]`: なし

## checklist

- [x] implement-from-docs-v2 の役割境界を確認した。
  - 検証結果: 指摘なし
  - 確認根拠: `.codex/skills/implement-from-docs-v2/SKILL.md` の Overview / Workflow / Rules / Done Criteria を読み、検証役は生成役の報告、実行ログ、証跡、差分を確認し、不足する証跡を自分で補完せず issue 化または追加依頼対象として報告する役割であることを確認した。

- [x] review-artifacts の checklist 記録形式を確認した。
  - 検証結果: 指摘なし
  - 確認根拠: `.codex/skills/review-artifacts/references/checklist-record-format.md` は各 `- [x]` に `検証結果` と `確認根拠` を記録し、`- [x]` は合格ではなく検証処理完了を示すと定義している。

- [x] 総合テスト方針が Playwright 実機確認を要求しているか確認した。
  - 検証結果: 指摘なし
  - 確認根拠: `docs/04_テスト/04_総合テスト/総合テスト方針.md` は、総合テストは利用者が Web 画面から業務を完了できることを確認し、Chrome の Playwright で検査できる画面操作、表示確認、画面遷移、スクリーンショット取得を Playwright で実施すると定義している。

- [x] Playwright 利用方針で検査対象になる操作範囲を確認した。
  - 検証結果: 指摘なし
  - 確認根拠: `総合テスト方針.md` の Playwright 利用方針は、フォーム入力、ボタン操作、画面遷移、ログイン、設定ダイアログ操作、履歴選択、削除メニュー操作、SSE状態表示、回答表示、参照元ビューア表示、Codex成果物表示、利用者向けエラー表示を Playwright で実施すると定義している。

- [x] Playwright で検査しない範囲と integration evidence の扱いを確認した。
  - 検証結果: 指摘なし
  - 確認根拠: `総合テスト方針.md` は Cookie 属性、DB データ、ファイルシステム更新/削除などを HTTP/DB/ファイル確認で実施するとしている。一方で、画面操作・表示・遷移・SSE表示そのものを integration test の合格だけで代替してよいとは定義していない。

- [x] 公式 Playwright evidence が実際に支える ST ケースを確認した。
  - 検証結果: 指摘あり
  - 確認根拠: `OFFICIAL-playwright-screen-check.txt`、`OFFICIAL-playwright-account-screen-check.txt`、`OFFICIAL-playwright-password-screen-check.txt`、`OFFICIAL-playwright-password-validation-check.txt`、`OFFICIAL-playwright-account-delete-check.txt` の `ST-...: passed` 行を確認した結果、正式な ST ケースとして直接 Playwright 証跡を持つのは 21 件だった。総合テスト方針の全体ケース 101 件に対して不足している。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] 直接 Playwright 証跡で合格維持できるケース数を確認した。
  - 検証結果: 指摘なし
  - 確認根拠: `テスト仕様・結果/*.md` の証跡欄で `ST-*.png` を参照する合格ケースは、認証 9 件、アカウント管理 9 件、チャット実行 3 件の計 21 件であり、対応する Playwright ログにもケース ID と screenshot path が記録されている。

- [x] integration evidence のみで合格扱いになっている passed ケース数を確認した。
  - 検証結果: 指摘あり
  - 確認根拠: `テスト仕様・結果/*.md` の ST 行を確認したところ、Playwright/Chrome 操作や表示確認を手順に含むにもかかわらず、証跡が `OFFICIAL-backend-integration.txt` または `OFFICIAL-frontend-integration.txt` のみで `合格` になっている passed ケースは 79 件だった。内訳は認証 6 件、アカウント管理 13 件、チャット実行 21 件、キャンセル 9 件、履歴再表示 15 件、チャット削除 15 件。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] ST-CHAT-025 の扱いを確認した。
  - 検証結果: 指摘なし
  - 確認根拠: `ST-CHAT-025` は Playwright 画面操作ではなく Codex Docker 実行スモークであり、既に `保留` として記録されている。保留理由は Codex 認証 401 であり、Playwright 実機確認不足とは別の既存保留である。

- [x] round-3 の `合格100 / 保留1` サマリが Playwright 基準と整合するか確認した。
  - 検証結果: 指摘あり
  - 確認根拠: `OFFICIAL-playwright-screen-summary.txt` は `合格: 100件 / 部分確認: 0件 / 保留: 1件` としているが、同じファイルは対象を「認証、アカウント管理、チャット初期表示の画面確認、および backend/frontend integration evidence による再確認」と記録している。Playwright で確認できるべきケースを integration evidence だけで合格扱いしているため、追加前提と整合しない。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] 総合テスト仕様・結果の再分類案を確認した。
  - 検証結果: 指摘あり
  - 確認根拠: Playwright 実機確認基準では、直接 Playwright 証跡のある 21 件だけ合格維持可能である。integration evidence のみで合格扱いされている 79 件は、Playwright 確認の追加または確認不能理由の明記まで保留へ戻すべきである。既存保留 `ST-CHAT-025` と合わせると、現時点の妥当な分類は合格 21 件 / 保留 80 件 / 判断不能 0 件である。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] 画面操作・表示確認の不足代表例を確認した。
  - 検証結果: 指摘あり
  - 確認根拠: `ST-AUTH-014`、`ST-ACCOUNT-005`、`ST-ACCOUNT-010`、`ST-ACCOUNT-016`、`ST-CHAT-013`、`ST-CHAT-015`、`ST-HISTORY-001`、`ST-DELETE-001` は、いずれも Playwright での画面操作または表示確認を手順に含むが、公式記録では backend/frontend integration evidence を根拠に合格扱いされている。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] ブラウザコンテキストを含むケースの証跡妥当性を確認した。
  - 検証結果: 指摘あり
  - 確認根拠: `ST-AUTH-015`、`ST-ACCOUNT-022`、`ST-DELETE-005`、`ST-DELETE-006`、`ST-DELETE-007` は複数 Chrome ブラウザコンテキストや別ブラウザ競合を前提にしているが、公式証跡は integration evidence のみで、複数 Chrome コンテキストの Playwright 実機確認ログや screenshot がない。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] SSE状態表示を含むケースの証跡妥当性を確認した。
  - 検証結果: 指摘あり
  - 確認根拠: `ST-CHAT-006`、`ST-CHAT-015`、`ST-CHAT-016`、`ST-HISTORY-004`、`ST-HISTORY-013`、`ST-HISTORY-014`、キャンセル系 `ST-CANCEL-001` から `ST-CANCEL-009` は SSE 状態表示や終端表示を期待するが、公式記録では integration evidence だけで合格扱いされている。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] 参照元ビューアと Codex 成果物表示を含むケースの証跡妥当性を確認した。
  - 検証結果: 指摘あり
  - 確認根拠: `ST-CHAT-009`、`ST-CHAT-010`、`ST-CHAT-020`、`ST-CHAT-021`、`ST-CHAT-022`、`ST-HISTORY-006`、`ST-HISTORY-007`、`ST-HISTORY-011`、`ST-HISTORY-012` は参照元ビューアまたは回答内 Codex 成果物表示を確認対象にしているが、Playwright 画面証跡ではなく integration evidence のみで合格扱いされている。
  - 指摘: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] 既存 Playwright 実機確認基準 issue の妥当性を判定した。
  - 検証結果: 指摘なし
  - 確認根拠: `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md` の指摘趣旨は、総合テスト方針、公式 evidence、テスト仕様・結果と整合している。件数は今回の読み取りでは「直接 Playwright 証跡なしの passed ケース 79 件」と見るのが安全だが、既存 issue の「78 件」という趣旨は削除理由にならない。

- [x] 既存全件合格未達 issue の妥当性を判定した。
  - 検証結果: 指摘なし
  - 確認根拠: `.issue/implement-from-docs/2026-06-23_10-30-01_正式総合テストが全件合格に達していない.md` は、round-3 時点では `ST-CHAT-025` のみを保留としていたが、Playwright 基準を適用すると保留が 80 件へ増えるため、全件合格未達という結論は引き続き妥当である。

- [x] TBC 候補を判定した。
  - 検証結果: 指摘なし
  - 確認根拠: 今回の問題は TBC に隔離すべき仕様未確定事項ではなく、正式総合テストの実施・証跡・再分類不足である。`ST-CHAT-025` は環境認証待ち保留、Playwright 不足 79 件は追加実機確認または理由付き保留への再分類対象として扱うべきである。

- [x] 正式総合テスト合否を再判定した。
  - 検証結果: 指摘あり
  - 確認根拠: 総合テスト方針の完了条件は全ケース実施済み・全ケース合格・必要最小限のスクリーンショット証跡保存である。現状は Playwright 実機確認基準で合格維持できるケースが 21 件に留まり、80 件が保留相当のため、正式総合テストは不合格である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-23_10-30-01_正式総合テストが全件合格に達していない.md`
    - `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] アプリ完成可否と最終報告可否を再判定した。
  - 検証結果: 指摘あり
  - 確認根拠: 正式総合テストが不合格で High issue 2 件が残るため、アプリ完成扱いは不可である。最終報告は、完成報告ではなく、Playwright 未確認 79 件、既存保留 `ST-CHAT-025`、再実施条件を明記する未完了報告としてのみ可能である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-23_10-30-01_正式総合テストが全件合格に達していない.md`
    - `.issue/implement-from-docs/2026-06-23_23-56-33_正式総合テストがPlaywright実機確認基準を満たしていない.md`

- [x] 今回レビューで実行系を行っていないことを確認した。
  - 検証結果: 対象外
  - 確認根拠: 検証役制限に従い、テスト実行、Playwright 実行、git 操作、CodeGraph、実装/docs修正、issue 作成は実施していない。
  - 理由: 今回の役割は既存成果物・証跡の読み取りレビューと checklist 作成に限定されているため。

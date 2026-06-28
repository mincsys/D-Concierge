# Workflow

管理役は、機能単位で生成役と検証役へ依頼を送る。検証役は生成役の作業完了後、`review-artifacts` checklist を作業用ディレクトリへコピーしてレビューする。

## 管理役の実行禁止ゲート

管理役は生成役・検証役の作業を代行しない。処理が遅い、待つより早い、簡単そう、少量作業、ユーザへ早く返したい、という理由でも肩代わりしない。

管理役は次を代行しない。

- テストコード作成
- 実装
- 総合テスト実行
- 証跡保存
- issue 修正
- 仕様書側修正
- レビュー
- 再レビュー
- issue 作成
- 完了可否判定
- 横断レビュー

管理役が直接行える作業は次に限定する。

- 機能分解
- 生成役・検証役への依頼送信
- 生成役・検証役の完了報告待ち
- `state.md` 更新
- タスクリスト更新
- 検証役の `削除可 issue` に基づく issue 削除、TBC 移動
- ステージング

管理役は、依頼した作業の完了報告を必ず待つ。完了報告がない状態で途中結果を使って成果物作成、修正、レビュー判定、機能結合完了判定、全体完了判定、次フェーズ移行をしない。

管理役は技術的な合否判断をしない。検証役の判定、生成役の報告、state、タスクリスト、issue/TBC 状態を照合し、手順上の完了条件が満たされているかだけを確認する。完了可否の根拠が不足する場合は、自分で判断せず検証役へ再確認するか、ユーザへ判断材料を添えて確認する。

Sandbox 環境で承認が必要なコマンドは、管理役または生成役が承認付きで実行する。承認が必要であることだけを理由に、テストを未実施、保留、`環境・承認待ち` にしない。ユーザが承認しない場合、または承認付き実行後も環境制約で実行不能な場合だけ、理由と承認付き実行結果を state へ記録して保留扱いにする。

## サブエージェント中断・再開

サブエージェントの完了メッセージが空、または実質的な完了報告を含まない場合、管理役はリミット到達による一時中断として扱う。

1. 管理役は、空完了メッセージを成功、失敗、TBC、レビュー完了として扱わない。
2. 管理役は次フェーズへ進まず、レビュー完了、機能結合完了、ステージング完了のチェックを付けない。
3. 管理役は state の `サブエージェント状態` に、対象役割、直前フェーズ、空完了メッセージ検知、リミット中断、再開時に渡す引き継ぎ要約を記録する。
4. 管理役はユーザへ一時中断を報告し、ユーザからリミット解除の指示があるまで作業を止める。
5. リミット解除後、管理役は前回の同一サブエージェントへ `send_input` で再利用再開を依頼する。
6. 前回サブエージェントが利用不能、文脈喪失、または再利用できない場合だけ、管理役は同じ役割のサブエージェントを新規起動する。
7. 再利用再開または新規再起動では、管理役は [handoff.md](../../subagent-protocol/resume/handoff.md) に従い、`SKILL.md` の軽読、前回状態、未完了作業、禁止事項、完了報告形式を渡す。
8. 再開後も、管理役はサブエージェントの正式な完了報告を受け取るまで次フェーズへ進まない。

## 機能ごとの基本順序

1. 管理役が機能 ID、機能概要、関連 docs、前提機能を state に記録する。
2. 管理役が [subagent-request-rules.md](../agents/subagent-request-rules.md) と [test-code.md](../../subagent-protocol/generator/test-code.md) に従い、受け手視点で書かれた依頼文を使って、生成役へ [test-first-flow.md](../testing/test-first-flow.md) に基づく単体・結合テストコード先行作成を依頼する。
3. 生成役完了後、管理役が [test-code-review.md](../../subagent-protocol/verifier/test-code-review.md) に従い、検証役へテストコード検証を依頼する。依頼には `review-artifacts` の `test` checklist 保存先 `.tmp/implement-from-docs-v2/features/<機能ID>/review-checklists/01_test-code/round-<n>/`、指摘保存先 `.issue/implement-from-docs/`、レビュー対象、報告形式を含める。
4. テストコード初回レビュー完了後、管理役が Red 確認結果、検証結果、issue 管理結果を state に記録し、v2 作業差分をステージングする。
5. 必要な修正がある場合は、ステージング後に [issue-fix.md](../../subagent-protocol/generator/issue-fix.md) と [rereview.md](../../subagent-protocol/verifier/rereview.md) に従い、最大 3 回まで生成役と検証役でループする。各再レビュー完了後も、管理役が state 更新、issue 管理、v2 作業差分のステージングを毎回行ってから次の修正依頼または次フェーズへ進む。
6. テストコード検証後、管理役が [implementation-and-integration-tests.md](../../subagent-protocol/generator/implementation-and-integration-tests.md) に従い、生成役へ [tdd-flow.md](../testing/tdd-flow.md) に基づく実装、単体テスト、[integration-contract-tests.md](../testing/integration-contract-tests.md) に基づく結合テスト、[quality-gates.md](../testing/quality-gates.md) に基づくカバレッジ確認を依頼する。
7. 生成役完了後、管理役が [integration-and-quality-review.md](../../subagent-protocol/verifier/integration-and-quality-review.md) に従い、検証役へ結合テスト完了検証と実装品質レビューを依頼する。依頼には `review-artifacts` の `implementation`、`test`、`evidence` checklist 保存先 `.tmp/implement-from-docs-v2/features/<機能ID>/review-checklists/02_integration-and-implementation-quality/round-<n>/`、指摘保存先 `.issue/implement-from-docs/`、レビュー対象、報告形式を含める。
8. 結合テスト完了検証の初回レビューまたは再レビュー完了後、管理役が state 更新、検証役の `削除可 issue` に基づく issue 削除、TBC 移動、v2 作業差分のステージングを毎回行う。
9. 結合レビュー通過後、管理役が [feature-system-test.md](../../subagent-protocol/generator/feature-system-test.md) に従い、生成役へ機能別総合テストを依頼する。生成役は `docs/04_テスト/04_総合テスト/` 全体を `.tmp/implement-from-docs-v2/features/<機能>/system-test/` へコピーし、正式総合テストと同じ流れ、同じ記録形式、同じ evidence 保存方針でコピー側へ結果と証跡を保存する。`docs/04_テスト/04_総合テスト/` は変更しない。
10. 生成役完了後、管理役が `git status --short`、`git diff -- docs/04_テスト/04_総合テスト`、必要に応じて `.tmp` 側差分を取得し、[feature-system-test-review.md](../../subagent-protocol/verifier/feature-system-test-review.md) に従い、検証役へ機能別総合テスト結果、証跡、分類、`docs` 非変更確認を依頼する。依頼には `review-artifacts` の `test`、`evidence` checklist 保存先 `.tmp/implement-from-docs-v2/features/<機能ID>/review-checklists/03_feature-system-test/round-<n>/`、指摘保存先 `.issue/implement-from-docs/`、レビュー対象、報告形式を含める。
11. 機能別総合テストレビューの初回レビューまたは再レビュー完了後、管理役が state 更新、検証役の `削除可 issue` に基づく issue 削除、TBC 移動、v2 作業差分のステージングを毎回行う。
12. 機能別総合テストに `不合格` または未分類の未実施が残る場合、管理役は機能結合完了にしない。`後続機能待ち`、`環境・承認待ち`、`対象外`、`部分確認` は、検証役が妥当と判定し、state の `正式総合テストへの持ち越し` に記録した場合だけ機能結合完了へ進める。
13. 検証役の結合レビューと機能別総合テストレビューの判定に基づき、管理役がタスクリストへ `機能結合完了` のチェックを付ける。

## 全機能後の正式総合テスト順序

1. 管理役が、対象範囲の全機能で機能結合完了になっていることをタスクリストと各 `state.md` で確認する。
2. 管理役が各機能 state の `正式総合テストへの持ち越し` を `.tmp/implement-from-docs-v2/system-test/state.md` に集約し、対象機能一覧、結合完了済み機能、参照する総合テスト仕様一覧、機能別総合テスト集約、正式総合テスト重点確認項目を記録する。
3. 管理役が検証役へ正式総合テスト前の横断レビューを依頼する。依頼には `review-artifacts` checklist 保存先 `.tmp/implement-from-docs-v2/system-test/review-checklists/cross-review/round-<n>/`、指摘保存先 `.issue/implement-from-docs/`、レビュー対象、報告形式を含める。
4. 横断レビューで指摘がある場合、管理役は正式総合テストへ進まず、[review-loop.md](review-loop.md) に従って最大 3 回まで生成役と検証役の修正ループを回す。横断レビューの issue が未解消、判断不能、TBC 候補、仕様書側修正のまま残る場合、管理役はその状態を state とタスクリストに記録し、アプリ完成とは扱わない。
5. 横断レビュー通過後、管理役が [official-system-test.md](../../subagent-protocol/generator/official-system-test.md) に従い、生成役へ既存の `テスト仕様・結果` に基づく正式総合テスト実行、結果記録、証跡保存、保留理由記録を依頼する。`.tmp` の機能別総合テスト結果は参考情報であり、正式結果として転記しない。
6. 生成役完了後、管理役が [official-system-test-review.md](../../subagent-protocol/verifier/official-system-test-review.md) に従い、検証役へ正式総合テスト結果分析レビュー、証跡確認、未ステージ差分確認、最終実装品質チェックを依頼する。依頼には `review-artifacts` の `implementation`、`test`、`evidence` checklist 保存先 `.tmp/implement-from-docs-v2/system-test/review-checklists/system-final/round-<n>/`、指摘保存先 `.issue/implement-from-docs/`、レビュー対象、報告形式を含める。
7. 検証役は正式総合テストの不合格・保留を `修正可能 / 仕様不整合 / テスト不能 / TBC候補` に分類する。修正可能な問題と仕様不整合は issue 化し、原因分類と推奨修正方針を記録する。テスト不能は自動操作不可、外部認証不足、環境制約など、生成役の修正では解消できない場合に限る。
8. 総合テスト結果分析レビューの初回レビューまたは再レビュー完了後、管理役が全体 state 更新、検証役の `削除可 issue` に基づく issue 削除、TBC 移動、v2 作業差分のステージングを毎回行う。
9. 正式総合テスト結果分析レビューで issue が作成された場合、管理役は [issue-fix.md](../../subagent-protocol/generator/issue-fix.md) に従い、生成役へ issue 修正、関連テスト、該当総合テスト再実行、証跡更新を依頼する。
10. 生成役の修正完了後、管理役は [rereview.md](../../subagent-protocol/verifier/rereview.md) に従い、検証役へ同一フェーズ全体の再レビューを依頼する。テスト不能項目以外が全て合格するまで、最大 3 回まで修正ループを繰り返す。
11. 3 回で解消しない総合テスト issue、仕様書側修正 issue、検証役が TBC 候補とした issue は、管理役が `.issue/implement-from-docs/TBC/` へ移動し、state とタスクリストへ未解決として記録する。TBC 移動は完成、合格、解消ではない。
12. 管理役が [final-report.md](../finalization/final-report.md) に従い、最終報告を作成する。

## 並行化ルール

- 検証は生成役の作業完了後に実施する。
- 管理役は、生成役と検証役が同じファイルを同時編集するような依頼を出さない。
- レビューまたは再レビュー完了後のステージング、検証役の `削除可 issue` に基づく issue 削除、TBC 移動、state 更新、タスクリスト更新は管理役だけが行う。
- `git status`、`git diff`、staged 差分などの差分情報は、コマンドを実行できる管理役が取得して検証役へ渡す。検証役にコマンド実行させない。
- 管理役が取得する差分情報やステージングで Sandbox 承認が必要な場合も、承認付きで実行する。承認が必要であることを理由に検証依頼やステージング境界を省略しない。

## 完了判断

- 管理役は検証役の結合完了判定なしに機能結合完了扱いしない。
- 管理役は機能別総合テストレビューなしに機能結合完了扱いしない。
- 管理役は正式総合テスト前の横断レビュー通過、正式総合テスト合格、総合テスト結果分析レビュー、必要な修正ループなしに最終完了扱いしない。
- 正式総合テスト不合格、TBC 残、High issue 残、または通常 issue の TBC 残存のいずれかがある場合、管理役はアプリ完成と表現しない。
- 検証打ち切り時は issue を TBC へ移動し、state とタスクリストへ未解決として記録する。TBC 残存のまま次フェーズまたは次機能へ進むのは独立作業を継続するためであり、当該対象の完了やアプリ完成を意味しない。
- `.tmp/implement-from-docs-v2/` は最終成果物ではないが、削除はユーザが行う。管理役、生成役、検証役は削除しない。

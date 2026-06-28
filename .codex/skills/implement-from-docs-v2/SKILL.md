---
name: implement-from-docs-v2
description: Implement software from docs by having a manager decompose work into verifiable feature tasks, reuse generator and verifier subagents, create unit and integration tests before implementation, complete integration and feature-level system-test review for every feature using .tmp copies of the official system-test specs/evidence, run cross-review before final official system tests, then run official system tests against docs and loop on verifier-created issues for fixable failures or holds under .issue/implement-from-docs.
---

# Implement From Docs v2

## Overview

docs を正として、管理役、生成役、検証役の 3 役で実装、テスト、検証を進める。v1 の docs-first、TDD、単体・結合・総合テスト、品質ゲートを維持しつつ、v2 では機能単位の開発を結合テストと機能別総合テストまで細かく回し、全機能の機能結合完了後、正式総合テストを実施する。

管理役は機能単位への分解、サブエージェントへの依頼、状態更新だけを担う。生成役はテスト方針書と設計書から単体・結合テストコードを先行作成し、機能別には実装、結合テスト、`.tmp` 上の機能別総合テストまでを行う。機能別総合テストでは正式総合テストと同じ仕様書、記録形式、evidence 保存方針を使うが、`docs/04_テスト/04_総合テスト/` は変更せず、`.tmp/implement-from-docs-v2/features/<機能>/system-test/` にコピーした作業用ファイルへ結果と証跡を保存する。全機能の機能結合完了後、検証役が横断レビューを行い、指摘がある場合は正式総合テストへ進む前に修正ループを回す。横断レビュー通過後、生成役が `docs/04_テスト/04_総合テスト/` を初めて更新する正式総合テストを行う。検証役は各レビュー時に `review-artifacts` のチェックリストを `.tmp` の対象フェーズへコピーして確認し、テストコード、結合テスト、機能別総合テスト、実装品質、正式総合テスト、完了可否を判定する。正式総合テストで不合格または保留が残る場合、検証役は単なる差し戻しではなく原因分析と issue 作成を行い、管理役は修正可能な issue を生成役へ修正させる。

## Workflow

1. [reading-order.md](references/core/reading-order.md) に従って docs、既存実装、テスト、設定、証跡、既存 issue を読む。
2. 実装対象が曖昧な場合だけ、ユーザへ 1 問ずつ確認する。
3. [startup.md](references/core/startup.md) と [subagent-request-rules.md](references/agents/subagent-request-rules.md) に従い、生成役と検証役を 1 回だけ起動する。モデル、reasoning、service tier は指定せず、親の構成を継承する。初回起動、再利用再開、新規再起動時はいずれも、この `SKILL.md` を軽く読ませ、役割境界と完了条件を理解させる。
4. 管理役、生成役、検証役は、それぞれ初期 docs 読込フェーズを行う。
5. [feature-decomposition.md](references/core/feature-decomposition.md) に従い、対象を検証可能な機能単位へ分解する。
6. [manager-tasklist-format.md](references/core/manager-tasklist-format.md) と [state-file-format.md](references/core/state-file-format.md) に従い、`.tmp/implement-from-docs-v2/` 配下へ管理用ファイルを作成する。
7. 各機能で、[workflow.md](references/orchestration/workflow.md)、[test-first-flow.md](references/testing/test-first-flow.md)、[tdd-flow.md](references/testing/tdd-flow.md)、[integration-contract-tests.md](references/testing/integration-contract-tests.md) に従い、単体・結合テストコード先行作成、テストコード検証、実装、結合テスト、結合レビュー、機能別総合テスト、機能別総合テストレビューを順に回し、機能結合完了まで進める。
8. 各レビュー依頼では、`review-artifacts` のチェックリスト保存先、指摘保存先、レビュー対象、報告形式を明示する。指摘保存先は `.issue/implement-from-docs/` とする。
9. 結合テスト完了時は [quality-gates.md](references/testing/quality-gates.md) と `review-artifacts` の `implementation`、`test`、`evidence` チェックリストに従い、カバレッジ、テスト品質、実装コード品質を確認する。
10. 検証役のレビューまたは再レビューが完了するたび、合否に関係なく [staging-boundary.md](references/orchestration/staging-boundary.md) に従って v2 作業差分をステージングする。
11. 指摘がある場合は [review-loop.md](references/orchestration/review-loop.md) に従い、最大 3 回まで生成役へ修正を依頼する。
12. 各機能の機能別総合テスト結果、保留分類、正式総合テストへの持ち越しを全体 state に集約する。
13. 全機能の機能結合完了後、検証役へ横断レビューを依頼する。横断レビューで指摘がある場合は、正式総合テストへ進まず [review-loop.md](references/orchestration/review-loop.md) に従い最大 3 回まで修正ループを行う。
14. 横断レビュー通過後、生成役へ既存の総合テスト方針と `テスト仕様・結果` に基づく正式総合テスト、結果記録、証跡保存を依頼する。正式総合テストでは `.tmp` の機能別総合テスト結果を参考情報として扱い、正式結果として転記しない。
15. 正式総合テスト完了後、検証役へ総合テスト結果分析レビューと最終実装品質チェックを依頼する。検証役は不合格・保留を `修正可能 / 仕様不整合 / テスト不能 / TBC候補` に分類し、修正可能な問題と仕様不整合は issue 化する。
16. 正式総合テスト結果分析レビューで issue が作成された場合、管理役はテスト不能項目以外が全て合格するまで最大 3 回まで生成役と検証役の修正ループを回す。生成役は issue 修正、関連テスト、該当総合テスト再実行、証跡更新を行う。
17. issue は [issue-lifecycle.md](references/orchestration/issue-lifecycle.md) に従い、`.issue/implement-from-docs/` 配下で管理する。
18. 横断レビュー、正式総合テスト、総合テスト結果分析レビュー、必要な修正ループ後、[manager-completion-checklist.md](references/finalization/manager-completion-checklist.md) で完了前確認を行い、[final-report.md](references/finalization/final-report.md) に従って最終報告する。

## Rules

- Active mode と承認ルールを守る。Plan Mode では実装せず、実装計画を作る。
- Sandbox 環境で承認が必要なコマンドは、承認が必要であることだけを理由に保留、未実施、`環境・承認待ち` に分類しない。実行担当者は承認付きで実行し、ユーザが承認しない場合、または承認付き実行後も環境制約で実行不能な場合だけ保留分類にする。
- docs から一意に分かることをユーザへ質問しない。探索で解決できない仕様判断だけ質問する。
- 管理役だけが `.tmp/implement-from-docs-v2/tasklist/implementation-tasklist.md` を編集する。
- 管理役は機能分解と進行管理に集中し、個別テスト項目、編集候補ファイル一覧を作らない。
- 管理役は生成役・検証役の作業を代行しない。処理が遅い、待つより早い、簡単そう、少量作業、ユーザへ早く返したい、という理由でも肩代わりしない。
- 管理役は、テストコード作成、実装、総合テスト実行、証跡保存、issue 修正、仕様書側修正、レビュー、再レビュー、issue 作成、完了可否判定を代行しない。
- 管理役は、生成役・検証役へ依頼した作業について必ず完了報告を待つ。完了報告なしに成果物作成、レビュー判定、機能結合完了判定、全体完了判定、次フェーズ移行をしない。
- サブエージェントの完了メッセージが空、または実質的な完了報告を含まない場合は、成功、失敗、TBC、レビュー完了ではなく、リミット到達による一時中断として扱う。管理役は次フェーズへ進めず、state に中断理由、対象役割、直前フェーズ、再開時に渡すべき引き継ぎを記録し、ユーザからリミット解除の指示があるまで作業を止める。
- リミット解除後は、前回の同一サブエージェントへの `send_input` で再利用再開を依頼する。前回サブエージェントが利用不能、文脈喪失、または再利用できない場合だけ、同じ役割のサブエージェントを新規起動し、引き継ぎを渡す。
- サブエージェントの初回起動、再利用再開、新規再起動時は、この `SKILL.md` の Overview、Workflow、Rules、Done Criteria、Resources を軽く読ませ、自分の役割、他エージェントの役割、管理役との境界を理解させる。全 reference を毎回読ませるのではなく、依頼に必要な reference だけを追加で読ませる。
- 管理役は技術的な合否判断をしない。検証役の判定、生成役の報告、state、タスクリスト、issue/TBC 状態を照合し、手順上の完了条件が満たされているかを確認する責任を持つ。
- 管理役は、検証役が完了可と判定していない対象、TBC が残る対象、正式総合テスト不合格の対象を、完了またはアプリ完成と表現しない。判断に迷う場合は技術判断せず、検証役へ再確認するか、ユーザへ判断材料を添えて確認する。
- 生成役と検証役はタスクごとに作り直さず、同じサブエージェントを使い回す。
- 生成役と検証役はさらにサブエージェントを起動しない。
- 生成役は本実装より前に、テスト方針書と設計書から単体・結合テストコードを作る。
- 生成役は機能別に静的テスト、単体テスト、結合テスト、カバレッジ確認を実行し、結果、ログ、coverage summary を報告する。
- 生成役は機能別の結合レビュー後に、`docs/04_テスト/04_総合テスト/` 全体を `.tmp/implement-from-docs-v2/features/<機能>/system-test/` へコピーし、正式総合テストと同じ流れ、同じ記録形式、同じ evidence 保存方針で機能別総合テストを実行、記録、証跡保存する。
- 生成役は機能別総合テストで `docs/04_テスト/04_総合テスト/` を変更しない。
- 生成役は全機能の機能結合完了後、既存の総合テスト方針と `テスト仕様・結果` に従って正式総合テストを実行、記録、証跡保存する。正式総合テストでは `docs/04_テスト/04_総合テスト/` を更新する。
- 正式総合テストで不合格または保留となった項目を、単なる再実行または証跡追加だけで完了扱いにしない。検証役が原因分析して issue 化した場合、生成役は指定 issue に従って実装、設定、テストデータ、テスト手順、仕様書、証跡の必要箇所を修正し、関連テストと該当総合テストを再実行する。
- 検証役は正式総合テストの不合格・保留を `修正可能 / 仕様不整合 / テスト不能 / TBC候補` に分類する。修正可能な問題は issue 化し、仕様不整合は推奨修正方針を含めて issue 化し、テスト不能は自動操作不可、外部認証不足、環境制約など生成役の修正で解消できない場合に限る。
- 管理役は正式総合テスト後、テスト不能項目以外が全て合格するまで最大 3 回の修正ループを回す。3 回で解消しない総合テスト issue は TBC へ移動できるが、アプリ完成または正式総合テスト合格とは扱わない。
- `.tmp/implement-from-docs-v2/` は最終成果物ではないが、削除はユーザが行う。管理役、生成役、検証役は `.tmp` 削除を担当せず、完了条件やステージング対象に `.tmp` 削除を含めない。
- TBC 移動は、3 回の修正ループで解消できない指摘を管理上隔離する処理であり、合格、解消、完成ではない。TBC が残る機能や総合テスト項目は、最終報告で未解決または未完成として扱う。
- Red 確認結果は生成役の完了報告に含め、管理役が `state.md` に要約する。テストコード、docstring、コメント、総合テスト仕様へ指定外の理由を書かない。
- 検証役は再レビューでも毎回ゼロベースで確認し、既存 issue の解消確認だけで終わらせない。
- 検証役はコマンドを実行しない。静的テスト、単体テスト、結合テスト、総合テスト、coverage summary 生成、証跡を保存するための実行は生成役が担当する。
- 検証役は生成役の報告、実行ログ、coverage summary、証跡、差分を確認する。結果や証跡が不足する場合は、自分で補完せず issue 化または生成役への追加依頼対象として報告する。
- 検証役はテスト方針・設計観点、カバレッジ、機能別総合テスト結果、正式総合テスト結果、証跡だけでなく、ディレクトリ構成、境界違反、コメント、コーディング規約など実装コード品質も確認する。
- 対象 issue があるレビューでは、検証役が issue を `解消済み / 未解消 / 判断不能 / TBC候補 / 仕様書側修正` に分類し、削除可否を報告する。管理役は検証役が `削除可 issue` に列挙した issue だけを削除し、独自に解消判断しない。
- 検証役の結合完了判定なしに、管理役は機能結合完了と判断しない。検証役の全体完了判定なしに、管理役は最終完了と判断しない。
- 検証役のレビューまたは再レビューが完了するたび、合否に関係なく v2 作業差分をステージングする。
- 作業開始時に既存の未コミット変更がある場合は、ステージング境界を壊さないためユーザ確認を挟む。
- 検証役レビューでは `review-artifacts` の checklist と指摘ファイル章構成を使う。v2 実行時の指摘保存先は `.issue/implement-from-docs/` とし、作業用 checklist は `.tmp/implement-from-docs-v2/` 配下のフェーズ別保存先へコピーする。
- 検証役レビューでは `review-artifacts` の `SKILL.md` に記載された Workflow に従い、未チェック項目をカテゴリ単位で検証する。記録形式は `review-artifacts/references/checklist-record-format.md` を使い、各 `- [x]` に `検証結果` と `確認根拠` を記録する。`- [x]` は合格ではなく、証拠付きで検証処理が完了したことを表す。
- 管理役は技術判断をしないが、検証役の checklist に未処理項目、根拠なし `- [x]`、完了可否へ反映されていない `指摘あり` または `判断不能` がある場合は、対象フェーズを完了扱いしない。
- `mock/` が存在する場合は [mock-visual-reference.md](references/testing/mock-visual-reference.md) に従い、見た目だけを参照し、mock 固有のデータ、状態、構成、業務ロジックを持ち込まない。
- sudo が必要な操作は実行せず、ユーザへ実行コマンドを提示する。

## Done Criteria

- ユーザが確定した対象範囲が、検証可能な機能単位へ分解されている。
- 管理役、生成役、検証役が初期 docs 読込フェーズを完了している。
- 生成役と検証役が同じサブエージェントとして使い回されている。
- 生成役と検証役が、初回起動、再利用再開、新規再起動時にこの `SKILL.md` を軽く読み、役割境界と完了条件を理解している。
- 管理役が生成役・検証役の作業を代行していない。
- 管理役が全ての生成役・検証役依頼について完了報告を待ってから次へ進んでいる。
- 空の完了メッセージまたは実質的な完了報告なしの応答が発生した場合、完了、失敗、TBC として扱わず、リミット到達による一時中断として state に記録し、ユーザのリミット解除後に再利用優先で再開している。
- 各機能で、テストコード、実装、結合テスト、結合レビュー、機能別総合テスト、機能別総合テストレビューが順序どおり処理され、機能結合完了まで進んでいる。
- 機能別総合テストでは、正式総合テストと同じ流れで `.tmp/implement-from-docs-v2/features/<機能>/system-test/` に結果と証跡が保存され、`docs/04_テスト/04_総合テスト/` が変更されていない。
- 全機能の機能結合完了後、正式総合テスト前に横断レビューが処理され、指摘がある場合は正式総合テストへ進む前に修正ループが処理されている。
- 横断レビュー通過後、正式総合テスト、証跡保存、総合テスト結果分析レビュー、最終実装品質チェック、必要な総合テスト issue 修正ループが処理されている。
- 検証役が、機能別のテストコード、結合テスト、機能別総合テスト、正式総合テストの各フェーズで `review-artifacts` の checklist を作業用ディレクトリへコピーし、未チェック項目をカテゴリ単位で証拠付きで処理している。
- 各 review-artifacts checklist に未処理項目と根拠なし `- [x]` が残っていない。
- `指摘あり` または `判断不能` の checklist 項目が、issue、state、完了可否のいずれにも反映されていない状態で残っていない。
- 検証役がコマンドを実行せず、生成役の報告、ログ、coverage summary、証跡、差分を確認している。
- 検証役が、結合テスト完了時と正式総合テスト完了時に実装コード品質レビューを実施している。
- テスト方針書と設計書から作成された単体・結合テストコードが検証役に承認されている。
- `.tmp/implement-from-docs-v2/tasklist/implementation-tasklist.md` は管理役だけが更新している。
- 検証役の各レビュー完了後に v2 作業差分がステージングされている。
- 検証役が `解消済み` と判定し `削除可 issue` に列挙した issue だけが管理役により削除され、打ち切り時の残 issue、仕様書側修正 issue、仕様不整合 issue は `.issue/implement-from-docs/TBC/` へ移動されている。
- 正式総合テストの不合格・保留が、検証役により原因分析され、修正可能 issue、仕様不整合 issue、テスト不能項目、TBC 候補として分類されている。
- 正式総合テスト後の修正可能 issue が、最大 3 回の修正ループで処理されている。
- 正式総合テストが合格し、未分類の保留事項が残っていない。
- 正式総合テスト不合格、TBC 残、High issue 残、または通常 issue の TBC 残存のいずれかがある場合、アプリ完成と表現していない。
- 管理役が、検証役の判定、生成役の報告、state、タスクリスト、issue/TBC 状態を照合し、手順上の完了条件を満たしていない対象を完了と表現していない。
- 検証役が完了不可と判定した対象を、最終報告で完了と表現していない。

## Resources

必要な resource のみ参照。`references/` は手順と判定境界、`subagent-protocol/` は依頼テンプレート。

- `references/`
    - `core/`
        - [reading-order.md](references/core/reading-order.md): 初期調査の読む順序。
        - [startup.md](references/core/startup.md): 初期読込とサブエージェント起動・再開の手順。
        - [feature-decomposition.md](references/core/feature-decomposition.md): 実装対象を機能単位へ分解する基準。
        - [manager-tasklist-format.md](references/core/manager-tasklist-format.md): 管理役用タスクリストの書式。
        - [state-file-format.md](references/core/state-file-format.md): state ファイルと持ち越し記録の書式。
    - `orchestration/`
        - [workflow.md](references/orchestration/workflow.md): 機能別作業から最終報告までの進行順序。
        - [review-loop.md](references/orchestration/review-loop.md): レビュー後の修正ループと TBC の扱い。
        - [staging-boundary.md](references/orchestration/staging-boundary.md): ステージング対象と検証依頼に添える差分情報。
        - [issue-lifecycle.md](references/orchestration/issue-lifecycle.md): issue の作成、解消、TBC 移動の運用。
    - `testing/`
        - [test-first-flow.md](references/testing/test-first-flow.md): テストコード先行作成と Red 報告の流れ。
        - [tdd-flow.md](references/testing/tdd-flow.md): Red、Green、Refactor の実装順序。
        - [integration-contract-tests.md](references/testing/integration-contract-tests.md): 結合境界と契約テストの観点。
        - [quality-gates.md](references/testing/quality-gates.md): テスト、coverage、実装品質の通過条件。
        - [mock-visual-reference.md](references/testing/mock-visual-reference.md): `mock/` の参照範囲と持ち込み禁止事項。
    - `agents/`
        - [subagent-request-rules.md](references/agents/subagent-request-rules.md): サブエージェント依頼の共通ルール。
    - `finalization/`
        - [final-report.md](references/finalization/final-report.md): 最終報告の表現と未完成時の扱い。
        - [manager-completion-checklist.md](references/finalization/manager-completion-checklist.md): 管理役の完了前確認項目。
- `subagent-protocol/`
    - `bootstrap/`
        - [generator.md](subagent-protocol/bootstrap/generator.md): 生成役の初期読込テンプレート。
        - [verifier.md](subagent-protocol/bootstrap/verifier.md): 検証役の初期読込テンプレート。
    - `generator/`
        - [test-code.md](subagent-protocol/generator/test-code.md): テストコード作成依頼テンプレート。
        - [implementation-and-integration-tests.md](subagent-protocol/generator/implementation-and-integration-tests.md): 実装と結合テスト依頼テンプレート。
        - [feature-system-test.md](subagent-protocol/generator/feature-system-test.md): 機能別総合テスト依頼テンプレート。
        - [official-system-test.md](subagent-protocol/generator/official-system-test.md): 正式総合テスト依頼テンプレート。
        - [issue-fix.md](subagent-protocol/generator/issue-fix.md): issue 修正依頼テンプレート。
    - `verifier/`
        - [test-code-review.md](subagent-protocol/verifier/test-code-review.md): テストコードレビュー依頼テンプレート。
        - [integration-and-quality-review.md](subagent-protocol/verifier/integration-and-quality-review.md): 結合・品質レビュー依頼テンプレート。
        - [feature-system-test-review.md](subagent-protocol/verifier/feature-system-test-review.md): 機能別総合テストレビュー依頼テンプレート。
        - [official-system-test-review.md](subagent-protocol/verifier/official-system-test-review.md): 正式総合テスト最終レビュー依頼テンプレート。
        - [rereview.md](subagent-protocol/verifier/rereview.md): 修正後の再レビュー依頼テンプレート。
    - `resume/`
        - [handoff.md](subagent-protocol/resume/handoff.md): 中断後の再開引き継ぎテンプレート。

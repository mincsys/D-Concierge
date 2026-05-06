---
name: implement-from-docs
description: Implement software from a fixed Japanese waterfall docs structure with docs-first discovery, TDD Red-Green-Refactor, static tests during refactor, unit/integration coverage gates, process-design contract tests, and mock design matching when a mock directory exists. Use when Codex needs to produce implementation artifacts from docs/01_要件定義, docs/02_外部設計, docs/03_内部設計, docs/04_テスト, and docs/05_開発標準 while preserving documented architecture, interfaces, tests, and visual design.
---

# Implement From Docs

## Overview

docs 固定構成を正として実装、テスト、検証を進める。実装前に docs と既存コードを読み、TDD、静的テスト、単体・結合カバレッジ、mock デザイン一致、総合テスト前ゲートを守る。

## Workflow

1. まず [reading-order.md](references/reading-order.md) に従って docs、設定、既存実装、`.issue/` を読む。
2. 実装対象が明示されていない場合は、実装前にユーザへ質問し、全体実装か特定機能だけか、既存 `.issue/` を対象に含めるか、未解消 `.issue/` が残る場合の扱い、設計書で定義された任意成果物・設計補助資料を対象に含めるかを確定する。
3. 実装対象ごとに、対応する要件、外部 IF、画面、内部設計、クラス設計、処理設計、テスト方針、コーディング規約を紐づける。
4. [tasklist.md](references/tasklist.md) に従い、`.tmp/implement-from-docs/tasklist/implementation-tasklist.md` を作成し、作業完了ごとに更新する。
5. [tdd-implementation-flow.md](references/tdd-implementation-flow.md) に従い、`.tmp/implement-from-docs/` を一時作業ルート、`.tmp/implement-from-docs/contract-matrix/` を契約マトリクス専用領域として扱い、単体テスト用は `unit/`、結合テスト用は `integration/` 配下へ作成してから、Red、Green、Refactor の順で実装する。
6. 結合テストを追加するときは [integration-contract-tests.md](references/integration-contract-tests.md) を読み、処理設計書の契約を必ず反映する。
7. 総合テストへ進む前に [coverage-and-quality-gates.md](references/coverage-and-quality-gates.md) に従い、契約網羅ゲート、対象外範囲、カバレッジを順に確認する。
8. 完了前に [review-checklist.md](references/review-checklist.md) で確認する。

## Rules

- Active mode と承認ルールを守る。Plan Mode では実装せず、実装計画を作る。
- 実装対象未指定時は推測で着手しない。ユーザ回答で確定した対象範囲を作業中および最終報告の完了判定基準にする。
- docs から一意に分かることをユーザへ質問しない。探索で解決できない仕様判断だけ質問する。
- 仕様、設計、実装の乖離を見つけたら、握りつぶさず `.issue/` に記録する。解決した issue は削除または更新する。
- docs にない独自仕様、独自の外部 IF、独自画面導線、独自メッセージを実装しない。
- `mock/` が存在する場合は [mock-design-match.md](references/mock-design-match.md) に従い、デザイン実装だけを反映し、mock 固有のデータ、状態、構成、業務ロジックを持ち込まない。
- sudo が必要な操作は実行せず、ユーザへ実行コマンドを提示する。
- 対象外にした未実装、未解消 `.issue/`、未反映の任意成果物・設計補助資料は完了扱いせず、今回対象外として報告する。

## Done Criteria

- 対象実装が docs の責務分割、依存方向、IF、メッセージ、ログ、テスト方針と整合している。
- `.tmp/implement-from-docs/tasklist/implementation-tasklist.md` の今回対象タスクがすべて処理済みである。
- `.tmp/implement-from-docs/contract-matrix/unit/` と `.tmp/implement-from-docs/contract-matrix/integration/` 配下の契約マトリクスで、今回実装する関数、クラス、公開IF の全契約行が `単体テスト済み`、`結合テスト済み`、`対象外理由あり`、`未実装として.issue化` のいずれかに分類されている。
- 単体テストを伴う実装単位は Red、Green、Refactor の順序で進め、結合テストは機能、公開境界、処理契約ごとに必要なタイミングで追加されている。
- Refactor ごとに対象範囲の静的テストを実施している。
- 単体・結合カバレッジは、契約網羅ゲートを通過し、各テスト方針の対象外範囲を除外したうえで目標値を満たしている。
- mock が存在する場合、デザイン実装は一致し、mock 固有要素は本実装へ混入していない。
- 総合テスト前に、単体、結合、静的テストがすべて合格している。
- ユーザが確定した対象範囲に未処理契約が残る場合、最終報告で完了と表現しない。

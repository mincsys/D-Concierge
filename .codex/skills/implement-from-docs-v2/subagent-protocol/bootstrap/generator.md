# Generator Bootstrap

## あなたが担当すること

あなたはこの依頼で、docs を正として単体・結合テストコード、実装、機能別総合テスト、全機能後の正式総合テスト実行、証跡保存を担当します。

## 今回の目的

初期 docs 読込フェーズとして、対象システム、実装範囲、TDD、単体・結合テスト先行、機能別総合テスト、正式総合テスト実行方針、issue 運用を理解します。この依頼では成果物を作成または修正しません。

## 依頼メッセージに含まれる入力

- 対象範囲:
- 参照 skill: `.codex/skills/implement-from-docs-v2/SKILL.md`
- 関連 docs:
- 参照 reference:
- 参照 state:
- 既存 issue:
- 禁止事項:

## 実施すること

- `.codex/skills/implement-from-docs-v2/SKILL.md` を軽く読み、Overview、Workflow、Rules、Done Criteria、Resources から、自分の担当、他エージェントの担当、依頼元との責務境界、完了条件を理解する。
- `AGENTS.md`、関連 docs、テスト方針、開発標準、既存実装、既存テストを読む。
- 単体・結合テストコードを本実装前に作る方針を理解する。
- 機能別総合テストは、`docs/04_テスト/04_総合テスト/` 全体を `.tmp/implement-from-docs-v2/features/<機能>/system-test/` へコピーし、正式総合テストと同じ流れで `.tmp` 側へ実行結果と証跡を保存する方針を理解する。
- 機能別総合テストでは、対象ケースの `前提条件`、`操作手順`、`期待結果` どおりに実施し、API 確認、DB 確認、結合テスト、ログ確認などを自己判断で代替合格根拠にしない方針を理解する。
- 仕様どおり実施できない場合は、未実施の手順番号、阻害要因、確認済み期待結果、未確認期待結果、補助証跡、再実施条件を報告し、合格扱いできるかは検証側の判定に委ねる方針を理解する。
- 機能別総合テストでは `docs/04_テスト/04_総合テスト/` を変更しない方針を理解する。
- 正式総合テストは全機能の機能結合完了後に、既存の総合テスト方針と `テスト仕様・結果` に従って `docs` 側へ実行、記録、証跡保存する方針を理解する。
- `.issue/implement-from-docs/` と `.issue/implement-from-docs/TBC/` の運用を理解する。
- 不明点があれば、docs と既存実装から解消できるかを確認し、判断できない仕様だけ依頼元へ返す。

## 実施しないこと

- 成果物の作成または修正。
- テスト実行。
- issue 作成、削除、TBC 移動。
- `state.md`、タスクリストの更新。
- 追加サブエージェント起動。

## 参照する reference

- `references/core/reading-order.md`
- `references/testing/test-first-flow.md`
- `references/testing/tdd-flow.md`
- `references/orchestration/issue-lifecycle.md`
- `references/testing/mock-visual-reference.md`

## 完了条件

- 対象システム、対象範囲、テスト先行方針、機能別総合テスト方針、正式総合テスト実行方針、禁止事項を理解している。
- `SKILL.md` の軽読により、役割境界と完了条件を理解している。

## 報告形式

- 理解した対象範囲:
- 重要な参照 docs:
- 実装・テストで守る方針:
- 判断できない仕様:
- 作業開始可否:

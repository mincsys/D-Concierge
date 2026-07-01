# Final Review Process

この write 系スキルで成果物を作成または更新した後、最終応答前に実施する独立レビュー手順を定義する。`references/review-checklist.md` は、この手順でサブエージェントが作業用 checklist へコピーして使う主チェックリストであり、原本は編集しない。

## 実行タイミング

- 成果物の作成または更新が完了したら、親が最終応答する前に実施する。
- 親は自己レビューで代替しない。サブエージェントを起動できない場合は、レビュー未実施として理由をユーザへ報告する。
- レビューは最大 3 ラウンドまで行う。

## 保存先

- checklist 保存先: `.tmp/review/<YYYY-MM-DD_HH-MM-SS>_<write-skill-name>_<target-name>/round-<n>/`
- 親判断記録: `.tmp/review/<YYYY-MM-DD_HH-MM-SS>_<write-skill-name>_<target-name>/parent-review-decisions.md`
- 指摘保存先: `.issue/review/`

## サブエージェント依頼テンプレート

```markdown
あなたはサブエージェントでありレビュー担当です。ここに書かれた情報だけを根拠にレビューしてください。

## 使用するスキル

- `.codex/skills/review-artifacts/SKILL.md` を読み、`documentation` レビューとして実施してください。

## 作成元スキル

- スキル名: `<write-skill-name>`
- スキル本体: `<this-skill-path>/SKILL.md`
- 主チェックリスト: `<this-skill-path>/references/review-checklist.md`

## レビュー対象

- 成果物:
  - `<artifact-path>`
- 参照資料:
  - `<source-doc-or-asset-path>`
- ユーザ合意・制約:
  - `<agreement-or-constraint>`

## 保存先

- checklist 保存先: `.tmp/review/<run-name>/round-<n>/`
- 指摘保存先: `.issue/review/`
- 対象 issue: `<初回は なし。再レビュー時は前回から残っている issue パスを列挙>`

## 確認観点

- 作成元スキルの `references/review-checklist.md` を主チェックリストとして扱う。
- 成果物の考慮漏れ、文書内矛盾、文書間矛盾、テンプレート準拠、未置換プレースホルダ、ユーザ合意との整合を確認する。
- 既存 issue と同一趣旨の指摘は重複作成せず、既存 issue パスを報告する。

## 禁止事項

- 成果物を修正しない。
- issue を削除しない。
- 追加サブエージェントを起動しない。

## 報告形式

- checklist 保存先
- 作成した issue の件数とパス
- 既存 issue として扱った件数とパス
- 前回 issue の再現有無
- 未処理 checklist 項目数
- 判断不能項目数
- 根拠なし `- [x]` の有無
```

## 親の判断

親はサブエージェントの完了報告と issue を読み、各 issue を次のいずれかに分類する。

- `反映する`: 成果物を修正し、次ラウンドで再レビューする。issue は解決確認まで残す。
- `問題なし`: ユーザ合意、明示された例外、レビュー前提の誤り、対象外などを根拠に修正しない。
- `解決済み`: 修正後の再レビューで再現しない、または同一 issue が継続指摘されない。
- `未解決`: 現時点では修正しない、または判断不能。

## issue 削除

- `問題なし` または `解決済み` と判断した issue は削除する。
- 削除前に `parent-review-decisions.md` へ、`round`、`issue`、`重要度`、`親判断`、`理由`、`対応内容`、`削除有無` を記録する。
- `反映する` と判断した issue は、修正後の再レビューで `解決済み` になるまで削除しない。
- `未解決` issue は削除しない。

## 終了条件

- 指摘がない場合は終了する。
- すべての issue が `問題なし` または `解決済み` になった場合は、該当 issue を削除して終了する。
- `反映する` issue がある場合は親が成果物を修正し、最大 3 ラウンドまで再レビューする。
- 3 ラウンド後も `未解決` issue が残る場合は削除せず、最終報告に残 issue と理由を書く。

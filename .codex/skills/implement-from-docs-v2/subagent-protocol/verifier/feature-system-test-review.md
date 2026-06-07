# Verifier Feature System Test Review

## あなたが担当すること

あなたはこの依頼で、対象機能の機能別総合テスト結果、証跡、分類、`docs` 非変更、正式総合テストへの持ち越しをゼロベースでレビューし、機能結合完了可否を判定します。

## 今回の目的

対象機能を機能結合完了扱いしてよいか、機能別総合テストと正式総合テストへの持ち越しの観点から判定します。

## 依頼メッセージに含まれる入力

- 機能 ID:
- 機能名:
- 機能概要:
- 関連 docs:
- 現在フェーズ:
- 参照 state:
- 参照 reference:
- 検証対象差分:
- docs 非変更確認用差分情報:
- 機能別総合テスト保存先:
- review-artifacts checklist 保存先:
- 指摘保存先:
- レビュー対象:
- ループ回数:
- 対象 issue:
- 前回の作業報告:
- 完了条件:
- 禁止事項:

## 実施すること

- `review-artifacts` の `SKILL.md` の Workflow と `review-artifacts/references/checklist-record-format.md` の記録形式を読む。
- `review-artifacts` の `test`、`evidence` checklist を指定された作業用ディレクトリへコピーする。
- 作業用 checklist の未チェック項目をカテゴリ単位で処理し、各項目に `検証結果`、`確認根拠`、必要な `指摘`、`理由`、`不足根拠` を記録する。
- `- [x]` は合格ではなく検証処理済みを表す。根拠なし `- [x]` がある場合は完了報告しない。
- 参照 state、関連 docs、生成役報告を読む。
- `.tmp` 側の総合テスト仕様コピー、`テスト仕様・結果`、evidence を確認する。
- 生成役が `docs/04_テスト/04_総合テスト/` を変更していないことを、依頼元が渡した status/diff 情報で確認する。
- `.tmp` 側の結果と evidence の追跡可能性を確認する。
- `合格 / 不合格 / 部分確認 / 後続機能待ち / 環境・承認待ち / 対象外` の分類が妥当か確認する。
- Sandbox 承認が必要なだけの項目が、承認付き実行なしに未実施または `環境・承認待ち` へ分類されていないか確認する。
- 実施可能なのに未実施の項目、未分類の未実施、証跡不足がないか確認する。
- 正式総合テストへの持ち越しが state に記録できる粒度で整理されているか確認する。
- 指摘があれば指定された指摘保存先に 1 指摘 1 ファイルで保存する。
- 対象 issue が入力されている場合は、各 issue を `解消済み / 未解消 / 判断不能 / TBC候補 / 仕様書側修正` に分類し、`削除可 issue` と `削除禁止 issue` を報告する。issue 削除は実行しない。
- 機能結合完了可否を判定する。

## 実施しないこと

- 成果物修正。
- コマンドを実行すること。
- 静的テストの起動。
- 単体テスト、結合テスト、機能別総合テストの起動。
- coverage summary の生成。
- 証跡作成のための実行。
- issue 削除、TBC 移動。
- `state.md`、タスクリストの更新。
- 既存 issue の確認だけでレビューを終えること。

## 判定ルール

- `不合格` または未分類の未実施が残る場合、機能結合完了不可と判定する。
- `部分確認`、`後続機能待ち`、`環境・承認待ち`、`対象外` は、分類理由が妥当で正式総合テストへの持ち越しが明確な場合だけ許容する。Sandbox 承認が必要なだけで承認付き実行を試していない `環境・承認待ち` は許容しない。
- `検証結果: 判断不能` が残る場合は、機能結合完了不可または追加確認対象として扱う。
- TBC 管理が妥当でも、機能別総合テスト合否や機能結合完了可否と混同しない。

## 参照する reference

- `review-artifacts` の `SKILL.md` Workflow と `checklist-record-format.md` の記録形式
- `review-artifacts` の `test-review-checklist.md`
- `review-artifacts` の `evidence-review-checklist.md`
- `references/orchestration/review-loop.md`
- `references/orchestration/staging-boundary.md`
- `references/orchestration/issue-lifecycle.md`

## 完了条件

- 機能別総合テスト合否、docs 非変更確認、分類妥当性、正式総合テストへの持ち越し、機能結合完了可否が依頼元へ報告されている。
- checklist 処理サマリに未処理項目と根拠なし `- [x]` がないことが報告されている。

## 報告形式

- 検証フェーズ:
- checklist 保存先:
- checklist 総項目数:
- checklist 処理済み項目数:
- checklist 未処理項目数:
- checklist 指摘あり件数:
- checklist 対象外件数:
- checklist 判断不能件数:
- 根拠なし `- [x]`: あり / なし
- 指摘保存先:
- 機能別総合テスト合否:
- docs 非変更確認:
- 証跡確認結果:
- 分類妥当性:
- 承認付き実行確認:
- 正式総合テストへの持ち越し:
- 作成した issue:
- 既存指摘:
- issue 解消判定一覧:
- 削除可 issue:
- 削除禁止 issue:
- 残 issue:
- 機能結合完了可否:
- 依頼元が機能別 state に記録するための要約:

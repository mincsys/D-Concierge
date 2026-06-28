# Subagent Request Rules

管理役は、生成役と検証役へ依頼するときに、役割、入力、禁止事項、完了条件、報告形式を明確に渡す。依頼本文はこの reference へ直接書かず、`../subagent-protocol/` 配下のテンプレートを使う。

テンプレート本文では `管理役`、`生成役`、`検証役` という内部役割名を使わない。依頼を受けたサブエージェントが単独で理解できるように、`あなた`、`依頼元`、`前回の作業報告`、`レビュー結果`、`指摘ファイル` など、受け手視点の表現で書く。

## 共通入力

依頼を作る側は各依頼で次を埋める。

- 機能 ID
- 機能名
- 機能概要
- 関連 docs
- 現在フェーズ
- 参照 state
- 参照 reference
- 再開種別: 初回 / 再利用再開 / 新規再起動 / 通常依頼
- 前回サブエージェント状況
- 引き継ぎ要約
- 最新ユーザ制約
- ループ回数
- 対象 issue
- 検証対象差分
- review-artifacts checklist 保存先
- review-artifacts checklist 逐次処理: 必須
- 指摘保存先
- レビュー対象
- 報告形式
- 完了条件
- 禁止事項

正式総合テストフェーズでは、`機能 ID`、`機能名`、`機能概要` の代わりに `対象機能一覧`、`結合完了済み機能`、`全体 state`、`総合テスト仕様一覧`、`機能別総合テスト集約`、`正式総合テスト重点確認項目` を渡す。

機能別総合テストフェーズでは、通常の機能別入力に加えて、`機能別総合テスト保存先`、`総合テスト仕様コピー元`、`対応総合テスト仕様`、`主対象ケース ID`、`後続依存ケース ID`、`docs 非変更確認用差分情報`、`仕様どおり実施できなかったケース`、`補助証跡`、`保留妥当性確認対象`、`正式総合テストへの持ち越し候補` を渡す。

該当しない項目は `なし` と書く。省略してサブエージェントに推測させない。

## 共通ルール

- サブエージェント起動時にモデル、reasoning、service tier を指定しない。
- タスクごとに作り直さず、同じサブエージェントを使い回す。
- 初回起動、再利用再開、新規再起動時は `.codex/skills/implement-from-docs-v2/SKILL.md` を軽く読み、自分の役割、他エージェントの役割、依頼元との責務境界、完了条件を理解してから作業する。
- さらにサブエージェントを起動しない。
- 他者の変更を戻さない。
- 管理用タスクリストを編集しない。
- `state.md` は読み取り専用とし、更新が必要な内容は依頼元へ報告する。
- 生成役・検証役の完了報告そのものはファイル化しない。依頼元が必要な要約だけ `state.md` に記録する。
- 不明点は docs と既存実装から解消し、判断できない仕様だけ依頼元へ返す。

## 依頼元の責務境界

依頼元は、サブエージェントへ渡した作業を自分で実行しない。処理が遅い、待つより早い、簡単そう、少量作業、ユーザへ早く返したい、という理由でも代行しない。

依頼元は次をしない。

- 成果物作成
- 成果物修正
- テストコード作成
- 実装
- 総合テスト実行
- 証跡保存
- レビュー
- 再レビュー
- 完了可否判定
- サブエージェントからの完了報告がない状態で次フェーズへ進むこと

依頼元は、サブエージェントの作業完了報告を必ず待つ。応答が遅い場合でも、完了前の途中状態を使って依頼元が成果物を作成、修正、検証しない。

サブエージェントの完了メッセージが空、または実質的な完了報告を含まない場合、依頼元は成功、失敗、TBC、レビュー完了として扱わない。リミット到達による一時中断として state に記録し、ユーザからリミット解除の指示があるまで作業を止める。

リミット解除後は、まず前回の同一サブエージェントへ `send_input` で再利用再開を依頼する。前回サブエージェントが利用不能、文脈喪失、または再利用できない場合だけ、同じ役割のサブエージェントを新規起動する。再利用再開または新規再起動では、[handoff.md](../../subagent-protocol/resume/handoff.md) に従って引き継ぎを渡し、再開後の完了報告を待つ。

## 生成役の責務境界

生成役は成果物を作る役である。単体・結合テストコード、実装、機能別総合テスト結果、全機能後の正式総合テスト結果、証跡、仕様書側修正 issue に基づく docs 修正を担当する。

生成役は次をしない。

- タスクリスト更新
- `state.md` 更新
- 機能結合完了判定
- 全体完了判定
- issue 削除
- issue の TBC 移動
- レビュー結果の自己承認
- 追加サブエージェント起動

## 検証役の責務境界

検証役は成果物を検証し、完了可否を判定する役である。`review-artifacts` checklist の作業用コピーと issue ファイルは作成できる。対象 issue が入力された場合は、各 issue を `解消済み / 未解消 / 判断不能 / TBC候補 / 仕様書側修正` のいずれかに分類し、`削除可 issue` と `削除禁止 issue` を報告する。

検証役は `review-artifacts` の `SKILL.md` に記載された Workflow に従い、作業用 checklist の未チェック項目をカテゴリ単位で証拠付きで処理する。記録形式は `review-artifacts/references/checklist-record-format.md` を使う。`- [x]` は合格ではなく検証処理済みを表す。

検証役は次をしない。

- 成果物修正
- タスクリスト更新
- `state.md` 更新
- 生成作業
- issue 削除
- issue の TBC 移動
- 追加サブエージェント起動

検証役は issue の削除可否を判定できるが、削除は実行しない。`削除可 issue` に含めてよいのは `解消済み` と判定した issue だけである。`未解消`、`判断不能`、`TBC候補`、`仕様書側修正` は `削除禁止 issue` に含める。

## 検証役の checklist 報告

検証役の完了報告には次を含める。

- checklist 保存先
- 総項目数
- 処理済み項目数
- 未処理項目数
- 指摘あり件数
- 対象外件数
- 判断不能件数
- 根拠なし `- [x]` の有無

根拠なし `- [x]` または未処理項目がある場合、検証役は完了可と報告しない。

## テンプレート一覧

- 生成役初期読込: [generator.md](../../subagent-protocol/bootstrap/generator.md)
- 検証役初期読込: [verifier.md](../../subagent-protocol/bootstrap/verifier.md)
- サブエージェント再開引き継ぎ: [handoff.md](../../subagent-protocol/resume/handoff.md)
- 生成役テストコード作成: [test-code.md](../../subagent-protocol/generator/test-code.md)
- 検証役テストコードレビュー: [test-code-review.md](../../subagent-protocol/verifier/test-code-review.md)
- 生成役実装・結合テスト: [implementation-and-integration-tests.md](../../subagent-protocol/generator/implementation-and-integration-tests.md)
- 検証役結合レビュー: [integration-and-quality-review.md](../../subagent-protocol/verifier/integration-and-quality-review.md)
- 生成役機能別総合テスト: [feature-system-test.md](../../subagent-protocol/generator/feature-system-test.md)
- 検証役機能別総合レビュー: [feature-system-test-review.md](../../subagent-protocol/verifier/feature-system-test-review.md)
- 生成役正式総合テスト: [official-system-test.md](../../subagent-protocol/generator/official-system-test.md)
- 検証役正式総合最終レビュー: [official-system-test-review.md](../../subagent-protocol/verifier/official-system-test-review.md)
- 生成役 issue 修正: [issue-fix.md](../../subagent-protocol/generator/issue-fix.md)
- 検証役再レビュー: [rereview.md](../../subagent-protocol/verifier/rereview.md)

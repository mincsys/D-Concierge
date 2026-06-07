---
name: review-artifacts
description: Review artifacts produced by .codex/skills, such as docs, src implementations, tests, evidence, and config files, for a user-specified target. Use when Codex needs to inspect generated artifacts, compare them with source documents and related outputs, and save each finding as a separate Markdown file under the default .issue/review/ directory or a user- or caller-specified findings directory without modifying the reviewed artifacts.
---

# Review Artifacts

## Overview

`.codex/skills/` によって作成された成果物を、ユーザが指定した対象に絞ってレビューする。対象は `docs/`、`src/`、テスト、証跡、設定ファイルなどの成果物であり、作成元スキルはレビュー基準として読むだけにする。

レビューで見つけた指摘は、チャット本文ではなく指摘保存先へ 1 指摘 1 ファイルで保存する。指摘保存先は、ユーザまたは呼び出し元スキルが明示した場合はその場所を使い、指定がない場合は `.issue/review/` を使う。レビュー実行中に対象成果物を修正しない。

## Workflow

1. ユーザ指定のレビュー対象を確認する。対象が曖昧な場合だけ、レビュー範囲を 1 問だけ確認する。
2. [scope-routing.md](references/scope-routing.md) と `レビュー種別` を読み、使用するレビュー種別と参照する checklist を決める。
3. 指摘保存先を決める。ユーザまたは呼び出し元スキルが `指摘保存先` を明示した場合はその場所を使い、指定がない場合は `.issue/review/` を使う。
4. [reading-order.md](references/reading-order.md) に従い、`AGENTS.md`、レビュー対象、関連成果物、対応する作成元スキル、使用する checklist、実際の指摘保存先にある既存指摘を読む。
5. checklist はレビュー観点として参照し、原本もコピーも更新しない。`- [ ]` を `- [x]` に変更する作業は行わない。
6. レビュー対象と関連成果物を確認し、仕様、設計、実装、テスト、証跡の乖離や品質問題を洗い出す。
7. 指摘が必要な場合は [finding-file-format.md](references/finding-file-format.md) に従い、指摘保存先へ 1 指摘 1 ファイルで保存する。同じ問題が既存 issue にある場合は、重複作成せず既存 issue パスを使う。
8. 最終応答では、作成した指摘ファイルと既存指摘の件数およびパスだけを報告する。指摘がない場合は `レビュー指摘はありませんでした。` と返す。他スキルから呼び出され、報告形式が明示された場合は、呼び出し元が求める判定項目も返してよい。

## レビュー種別

- `documentation`: [documentation-review-checklist.md](references/documentation-review-checklist.md) を使う。対応する作成元スキルの `references/review-checklist.md` がある場合は主チェックリストとして扱い、作業用ディレクトリへコピーする。原本は変更しない。
- `implementation`: [implementation-review-checklist.md](references/implementation-review-checklist.md) を使い、仕様、設計、実装、テスト、証跡を照合する。
- `test`: [test-review-checklist.md](references/test-review-checklist.md) を使い、テスト方針、テストコード、実行境界、カバレッジ、TDD の扱いを照合する。
- `evidence`: [evidence-review-checklist.md](references/evidence-review-checklist.md) を使い、証跡の保存場所、命名、ケース対応、記録項目を照合する。
- `cross-artifact`: [cross-artifact-review-checklist.md](references/cross-artifact-review-checklist.md) を必ず使い、docs、src、tests、evidence、設定、実行結果の追跡と整合を照合する。対象に応じて `documentation`、`implementation`、`test`、`evidence` の checklist も合わせて作業用ディレクトリへコピーする。

## Rules

- ユーザが明示しない限り、レビュー対象の成果物を修正しない。
- 作成元スキルは成果物の作成基準として読む。作成元スキルの品質評価や改善提案は扱わない。
- 仕様、設計、実装、テスト、証跡の乖離を見つけた場合は、通常の課題メモではなく指摘保存先のレビュー指摘として保存する。
- `修正方針` はゼロベースで書く。レビュー対象を必ず直す前提にせず、根拠に基づいて仕様、設計、実装、テスト、証跡、参照元文書のどれを直すべきかを示す。
- 重要度は `High`、`Medium`、`Low` の 3 段階だけを使う。
- 指摘タイトルは簡潔な日本語にする。
- 指摘ファイル名は `<指摘保存先>/YYYY-MM-DD_HH-MM-SS_<指摘タイトル>.md` とする。ファイル名では空白、スラッシュ、制御文字を `_` に置換する。
- 実際の指摘保存先を読み、同一趣旨の指摘を重複作成しない。
- 詳細なレビュー本文をチャットへ貼らない。
- checklist は観点として読むだけにし、原本、コピー、作業用 checklist のいずれも更新しない。
- `- [ ]` を `- [x]` へ変更しない。
- issue は独立した修正単位ごとに作る。同じ checklist 項目で見つかったという理由だけで、構造問題、仕様契約問題、テスト不足、証跡不足を 1 つの issue に混ぜない。
- issue の `根拠` はファイル名やパスだけの列挙にせず、どの成果物のどの内容を確認して何を根拠に指摘したかを文章で説明する。
- 他スキルから呼び出され、報告形式が明示された場合は、作成指摘、既存指摘に加えて、呼び出し元が求める判定項目を返してよい。
- 同一趣旨の既存指摘がある場合は重複ファイルを作らず、最終応答で既存指摘として示す。

## Done Criteria

- ユーザ指定のレビュー対象と関連成果物を読んでいる。
- 使用したレビュー種別に対応する reference を読んでいる。
- 使用したレビュー種別の checklist を観点として読んでいる。
- checklist 原本、コピー、作業用 checklist のいずれも更新していない。
- 文書レビューでは、対応する作成元スキルの `references/review-checklist.md` を主チェックリストとして扱っている。
- 文書レビューで作成元スキルのチェックリストを使う場合も、作成元スキルの原本が変更されていない。
- 指摘がある場合、すべて実際の指摘保存先へ 1 指摘 1 ファイルで保存されている。
- 指摘ファイルが `# 指摘タイトル`、`## 重要度`、`## レビュー対象`、`## 指摘内容`、`## 根拠`、`## 影響`、`## 修正方針` の章構成になっている。
- `修正方針` がレビュー対象の修正だけに固定されず、どの成果物を直すべきかを根拠から示している。
- 最終応答が、作成した指摘ファイルと既存指摘の件数およびパスだけになっている。他スキルから呼び出され、報告形式が明示された場合は、呼び出し元が求める判定項目を含んでよい。
- 指摘がない場合、最終応答が `レビュー指摘はありませんでした。` だけになっている。他スキルから呼び出され、報告形式が明示された場合は、呼び出し元が求める判定項目を含んでよい。

## Resources

- 読込順序: [reading-order.md](references/reading-order.md)
- 対象分類: [scope-routing.md](references/scope-routing.md)
- 文書レビュー: [documentation-review-checklist.md](references/documentation-review-checklist.md)
- 実装レビュー: [implementation-review-checklist.md](references/implementation-review-checklist.md)
- テストレビュー: [test-review-checklist.md](references/test-review-checklist.md)
- 証跡レビュー: [evidence-review-checklist.md](references/evidence-review-checklist.md)
- 横断レビュー: [cross-artifact-review-checklist.md](references/cross-artifact-review-checklist.md)
- 指摘ファイル形式: [finding-file-format.md](references/finding-file-format.md)

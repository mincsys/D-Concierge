# Evidence Review Checklist

## 証跡と方針の整合

- [x] 証跡の保存場所、ファイル名、記録項目が対応するテスト方針と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体証跡は `docs/04_テスト/02_単体テスト/evidence/backend-unit-coverage.txt`、結合証跡は `docs/04_テスト/03_結合テスト/evidence/backend-integration-evidence.txt` にあり、結合証跡には `design_coverage`、`tests`、`failures` が復元されている。
- [x] 証跡がどのテストケース、コマンド、範囲指定、実施日時に対応するか追跡できるか。
  - 検証結果: 指摘なし
  - 確認根拠: 両 evidence に `executed_at=2026-06-21T22:08:46+09:00` と coverage 付き pytest command が記録され、state には単体 105 passed、結合 51 passed の実行報告がある。
- [x] 証跡に対象コミット、対象差分、実行環境、主要バージョン、ブラウザ、画面サイズなど、再現に必要な前提が残っているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体・結合方針の coverage evidence は key=value の最小項目を正式証跡とし、ブラウザや画面サイズは今回対象外である。コマンドには `UV_CACHE_DIR=/tmp/uv-cache`、対象パス、coverage 出力条件が含まれる。
- [x] 再テスト時に古い証跡と新しい証跡の扱いが方針と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は同じファイル名で最新値へ上書きされ、差分上も 21:49 の値から 22:08 の値へ更新されている。
- [x] 証跡に秘密情報、個人情報、絶対パス、不要な詳細ログが含まれていないか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は target、executed_at、command、coverage、tests、failures、result のみで、DB URL、Cookie、パスワード、個人情報、絶対パス、詳細ログを含まない。

## カバレッジ証跡

- [x] 方針で指定された指標だけが記録されているか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は分岐 coverage、covered branches、total branches を記録し、行・ステートメント・関数 coverage を出力していない。結合 evidence は方針の `design_coverage` も含む。
- [x] 対象、実行日時、実行コマンド、カバレッジ値、総数、通過数、判定結果がそろっているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体 evidence は `target`、`executed_at`、`command`、`branch_coverage=96.32%`、`covered_branches=131`、`total_branches=136`、`result=pass` を含む。結合 evidence は同項目に加え `tests=51` と `failures=0` を含む。
- [x] 目標未達を合格扱いしていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体は方針の 95% 以上に対して 96.32%、結合は方針の 80% 以上に対して 80.26% で、いずれも `result=pass` と整合する。
- [x] 測定から外した範囲がテスト方針と矛盾していないか。
  - 検証結果: 指摘なし
  - 確認根拠: `pyproject.toml` の coverage omit は tests、`main.py`、database migrations であり、F002 application、REST、security、repository 実装を不当に除外していない。

## 総合テスト証跡

- [x] スクリーンショットやテキスト証跡がテストケースIDと対応しているか。
  - 検証結果: 対象外
  - 確認根拠: 今回は F002 結合・品質レビューであり、総合テストのケース別スクリーンショットやテキスト証跡はレビュー対象ではない。
  - 理由: 総合テスト証跡ではないため。
- [x] スクリーンショットやログが、ロード中、エラー画面、古い状態ではなく、判定対象の状態を示しているか。
  - 検証結果: 対象外
  - 確認根拠: 画面証跡やスクリーンショットは今回のレビュー対象に含まれず、backend coverage evidence を確認している。
  - 理由: 総合テスト証跡ではないため。
- [x] 必要最小限の証跡になっているか。
  - 検証結果: 対象外
  - 確認根拠: この項目は総合テスト証跡の粒度確認であり、今回の正式対象は単体・結合 coverage evidence である。
  - 理由: 総合テスト証跡ではないため。
- [x] 画面確認、HTTP確認、DB確認、ファイル確認の記録が、ケースの判定に必要な粒度で残っているか。
  - 検証結果: 対象外
  - 確認根拠: ケース別の総合テスト記録は未実施フェーズであり、今回の evidence は backend テスト全体の coverage summary である。
  - 理由: 総合テスト証跡ではないため。
- [x] 未実施、一部確認、保留、不合格、再テストが曖昧に合格扱いされていないか。
  - 検証結果: 対象外
  - 確認根拠: 機能別総合テストの未実施・保留記録は今回のレビュー対象外であり、結合テスト evidence では failures=0 と result=pass が記録されている。
  - 理由: 総合テスト証跡ではないため。
- [x] 証跡だけを見て、どのケースが合格、不合格、部分確認、未実施、保留なのか誤読なく分かるか。
  - 検証結果: 対象外
  - 確認根拠: 今回は総合テストケース別証跡ではなく、単体・結合の coverage evidence を確認している。
  - 理由: 総合テスト証跡ではないため。

## 実行結果の信頼性

- [x] 証跡の実行日時が対象成果物の変更後になっているか。
  - 検証結果: 指摘なし
  - 確認根拠: state の round-1 修正報告と evidence はいずれも 22:08:46 の実行結果として記録され、差分上も修正後 coverage 値へ更新されている。
- [x] 実行コマンドが方針書、設定、package manager、依存管理の現行定義と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence のコマンドは `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... --cov=src/backend --cov-branch` で、AGENTS.md の uv cache 指定とテスト方針の pytest/coverage 方針に沿っている。
- [x] 証跡と実際のテストコード、テスト仕様、設定ファイルに矛盾がないか。
  - 検証結果: 指摘なし
  - 確認根拠: state の単体 105 passed、結合 51 passed、coverage 96.32% / 80.26% と evidence の `tests=51`、`failures=0`、branch counts は整合している。`pyproject.toml` の coverage branch 設定とも一致する。
- [x] 同じ対象に対する古い証跡が残り、最新結果と誤認される状態になっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: backend 単体・結合 evidence は同一ファイルが最新値へ更新され、同じ evidence ディレクトリに F002 用の別名旧証跡は確認していない。

## 修正方針の判断

- [x] 証跡が不足している場合は、証跡の追加、再実行、テスト仕様更新のどれが必要かを書く。
  - 検証結果: 指摘なし
  - 確認根拠: 前回不足した結合 evidence の必須 key と format check 報告は補完済みであり、今回 evidence 不足として追加 issue 化すべき項目は確認していない。
- [x] 証跡が方針と矛盾する場合は、証跡を直すべきか、方針を直すべきかを根拠から判断する。
  - 検証結果: 指摘なし
  - 確認根拠: 修正後 evidence は単体・結合テスト方針の保存場所、key、coverage 指標、pass/fail 表現と矛盾しない。
- [x] 証跡だけでは判定不能な場合は、必要な再実行条件と対象成果物を具体的に書く。
  - 検証結果: 指摘なし
  - 確認根拠: evidence、state の実行報告、関連テスト本文、coverage 設定から今回の証跡判定は可能であり、証跡だけを理由に判断不能とする項目はない。

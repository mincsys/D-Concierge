# Evidence Review Checklist

## 証跡と方針の整合

- [x] 証跡の保存場所、ファイル名、記録項目が対応するテスト方針と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は `.tmp/implement-from-docs-v2/features/F004_execution_sse_cancel/system-test/evidence/` 配下に `F004-execution-sse-cancel-api-db.txt` と `F004-system-test-summary.txt` として保存され、F004 の API/SSE/DB/trace log 確認と分類 summary を分けている。
- [x] 証跡がどのテストケース、コマンド、範囲指定、実施日時に対応するか追跡できるか。
  - 検証結果: 指摘なし
  - 確認根拠: `F004-execution-sse-cancel-api-db.txt` は unit/integration command、実施日時、件数、結果を記録し、`F004-system-test-summary.txt` は pass/partial/followup/out_of_scope のケース ID を列挙している。
- [x] 証跡に対象コミット、対象差分、実行環境、主要バージョン、ブラウザ、画面サイズなど、再現に必要な前提が残っているか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は実施日時、実行コマンド、承認付き実行有無、Playwright 未実行理由を記録している。ブラウザと画面サイズは今回未実行で、正式総合テストへ持ち越す理由が記録されている。
- [x] 再テスト時に古い証跡と新しい証跡の扱いが方針と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 機能別総合テスト evidence は 2 ファイルに最新結果として記録され、古い結果が同一ファイル内で混在していない。
- [x] 証跡に秘密情報、個人情報、絶対パス、不要な詳細ログが含まれていないか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は feature ID、コマンド、件数、分類、確認内容、持ち越し候補を key=value で記録しており、秘密情報や個人情報は含まれていない。

## カバレッジ証跡

- [x] 方針で指定された指標だけが記録されているか。
  - 検証結果: 対象外
  - 確認根拠: 今回のレビュー対象は機能別総合テスト evidence であり、coverage evidence は結合・品質レビューで確認済み。
  - 理由: 機能別総合テスト evidence に coverage 指標は要求されていないため。
- [x] 対象、実行日時、実行コマンド、カバレッジ値、総数、通過数、判定結果がそろっているか。
  - 検証結果: 対象外
  - 確認根拠: F004 機能別総合テストの evidence は API/DB/SSE/trace log と分類 summary であり、coverage 値を記録する成果物ではない。
  - 理由: coverage 証跡の確認フェーズではないため。
- [x] 目標未達を合格扱いしていないか。
  - 検証結果: 対象外
  - 確認根拠: 機能別総合テストの合否は分類と evidence に基づき、coverage 閾値判定は今回対象外。
  - 理由: coverage 目標判定は結合・品質レビューで扱うため。
- [x] 測定から外した範囲がテスト方針と矛盾していないか。
  - 検証結果: 対象外
  - 確認根拠: coverage 測定範囲の判定ではなく、`.tmp` 側 system-test 結果のレビューを実施している。
  - 理由: coverage 測定対象外のレビューであるため。

## 総合テスト証跡

- [x] スクリーンショットやテキスト証跡がテストケースIDと対応しているか。
  - 検証結果: 指摘なし
  - 確認根拠: summary の `pass_items`、`partial_items`、`followup_items`、`out_of_scope_items` と、各 `テスト仕様・結果/*.md` の F004 実施結果行がケース ID 単位で対応している。
- [x] スクリーンショットやログが、ロード中、エラー画面、古い状態ではなく、判定対象の状態を示しているか。
  - 検証結果: 指摘なし
  - 確認根拠: Playwright screenshot は未実行であり、代替のテキスト evidence は API/SSE/DB/trace log の確認対象状態を `api_sse_confirmed`、`cancel_confirmed`、`startup_recovery_confirmed` として記録している。
- [x] 必要最小限の証跡になっているか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は 2 ファイルに限定され、詳細実行ログや不要なスクリーンショット、動画、trace は保存されていない。
- [x] 画面確認、HTTP確認、DB確認、ファイル確認の記録が、ケースの判定に必要な粒度で残っているか。
  - 検証結果: 指摘なし
  - 確認根拠: `manual_check` は API/DB/SSE/trace log 確認と明記し、HTTP/SSE、DB 状態、trace log の確認内容を evidence に残している。画面確認は正式総合テストへの持ち越し候補として分離されている。
- [x] 未実施、一部確認、保留、不合格、再テストが曖昧に合格扱いされていないか。
  - 検証結果: 指摘なし
  - 確認根拠: `classification_fail=0`、`classification_partial=12`、`classification_followup=19`、`classification_environment_wait=0`、`classification_out_of_scope=13` が明示され、未実施部分は後続機能待ちまたは正式総合テスト持ち越しとして整理されている。
- [x] 証跡だけを見て、どのケースが合格、不合格、部分確認、未実施、保留なのか誤読なく分かるか。
  - 検証結果: 指摘なし
  - 確認根拠: `F004-system-test-summary.txt` の分類別 item list と `.tmp` 側テスト仕様の F004 実施結果表により、合格 5、部分確認 12、後続機能待ち 19、対象外 13 が追跡できる。

## 実行結果の信頼性

- [x] 証跡の実行日時が対象成果物の変更後になっているか。
  - 検証結果: 指摘なし
  - 確認根拠: state では F004 結合・品質レビュー round-2 合格後に機能別総合テストへ進んでおり、evidence の `executed_at=2026-06-22T06:32:09+09:00` が機能別総合テスト結果として記録されている。
- [x] 実行コマンドが方針書、設定、package manager、依存管理の現行定義と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence の unit/integration command は `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` 形式で、AGENTS.md の uv/cache 指示と一致する。
- [x] 証跡と実際のテストコード、テスト仕様、設定ファイルに矛盾がないか。
  - 検証結果: 指摘なし
  - 確認根拠: `F004-execution-sse-cancel-api-db.txt` の確認内容は、`.tmp` 側のチャット実行・キャンセル・履歴再表示テストの F004 実施結果と対応している。
- [x] 同じ対象に対する古い証跡が残り、最新結果と誤認される状態になっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 機能別総合テスト evidence は feature ID 付きの 2 ファイルにまとまり、F002/F003 や結合 coverage evidence と混同しない配置になっている。

## 修正方針の判断

- [x] 証跡が不足している場合は、証跡の追加、再実行、テスト仕様更新のどれが必要かを書く。
  - 検証結果: 対象外
  - 確認根拠: 証跡不足は確認されず、追加実行や証跡更新の指摘は作成していない。
  - 理由: 修正方針を記録すべき証跡不足がないため。
- [x] 証跡が方針と矛盾する場合は、証跡を直すべきか、方針を直すべきかを根拠から判断する。
  - 検証結果: 対象外
  - 確認根拠: evidence と総合テスト方針の矛盾は確認していない。
  - 理由: 方針矛盾の指摘がないため。
- [x] 証跡だけでは判定不能な場合は、必要な再実行条件と対象成果物を具体的に書く。
  - 検証結果: 対象外
  - 確認根拠: `.tmp` 側テスト仕様、summary、API/DB/SSE/trace evidence、state の照合で判定可能だった。
  - 理由: 判断不能項目がないため。

# 証跡レビュー checklist

対象: F005 Codex実行・回答検証・採用保存 結合テスト完了検証・実装コード品質レビュー round-1

## 1. 証跡の配置・形式

- [x] 単体テストcoverage証跡が所定の場所にある
  - 検証結果: 適合
  - 確認根拠: `docs/04_テスト/02_単体テスト/evidence/backend-unit-coverage.txt` を確認した。
- [x] 結合テストcoverage証跡が所定の場所にある
  - 検証結果: 適合
  - 確認根拠: `docs/04_テスト/03_結合テスト/evidence/backend-integration-evidence.txt` を確認した。
- [x] 証跡がkey=value形式で記録されている
  - 検証結果: 適合
  - 確認根拠: `target`、`executed_at`、`command`、`branch_coverage`、`covered_branches`、`total_branches`、`result` 等がkey=valueで記録されている。
- [x] 実行日時と実行コマンドが記録されている
  - 検証結果: 適合
  - 確認根拠: 単体・結合とも `executed_at=2026-06-22T08:05:01+09:00` と coverage command を記録。
- [x] 証跡がF005実装後の最新結果を示している
  - 検証結果: 適合
  - 確認根拠: stateの生成役報告値と証跡のcoverage値、テスト数が一致している。

## 2. Coverage門番

- [x] 単体branch coverageが門番値を満たしている
  - 検証結果: 適合
  - 確認根拠: 単体 branch_coverage=95.74%、covered_branches=337、total_branches=352。
- [x] 結合branch coverageが門番値を満たしている
  - 検証結果: 適合
  - 確認根拠: 結合 branch_coverage=80.34%、covered_branches=376、total_branches=468。
- [x] failures=0が記録されている
  - 検証結果: 適合
  - 確認根拠: 結合証跡に `failures=0`、stateに結合99 passed。
- [x] coverage数値と生成役報告が矛盾していない
  - 検証結果: 適合
  - 確認根拠: ユーザ提示のevidence内容、state、証跡ファイルの数値が一致。

## 3. 結合証跡

- [x] 結合テストの対象範囲がdesign_coverageに記録されている
  - 検証結果: 適合
  - 確認根拠: F001-F004に加え、F005 fake Codex generation/validation、fixed validation、DB persistence、REST detail/SSE answer replay、validation failure が記録されている。
- [x] tests件数が記録されている
  - 検証結果: 適合
  - 確認根拠: `tests=99`。
- [x] 承認付き実行が必要な理由がstateに記録されている
  - 検証結果: 適合
  - 確認根拠: stateに PostgreSQL 接続を伴う結合テストとcoverageは承認付き実行でpassと記録。
- [x] 実Codexを起動しない確認範囲が報告に記録されている
  - 検証結果: 適合
  - 確認根拠: stateに「結合テストは承認付きで実行。実 Codex は起動していない」と記録。
- [x] 証跡が不合格や未完了を隠していない
  - 検証結果: 指摘あり
  - 確認根拠: 証跡値自体はpassだが、レビューで実API配線欠落などテスト未検出の不具合を5件issue化した。
- [x] 証跡の保存先が正本テスト証跡として妥当である
  - 検証結果: 適合
  - 確認根拠: 単体・結合の公式evidenceディレクトリに保存されている。

## 4. 再現性・信頼性

- [x] コマンドが再実行可能な形で記録されている
  - 検証結果: 適合
  - 確認根拠: `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... --cov=src/backend --cov-branch ...` が記録されている。
- [x] sandbox制約と承認付き実行の扱いが明確である
  - 検証結果: 適合
  - 確認根拠: DB接続を伴う結合実行は承認付きでpassとstateに記録。
- [x] 実行結果の成功/失敗が明確である
  - 検証結果: 適合
  - 確認根拠: 単体・結合とも `result=pass`。
- [x] レビュー時に実行系コマンドを再実行していない
  - 検証結果: 適合
  - 確認根拠: 本レビューではファイル本文・証跡・stateの読み取りのみで、pytest/ruff/mypy/app/DB/coverageは実行していない。

## 5. 指摘管理

- [x] 証跡不足があればissue化した
  - 検証結果: 該当なし
  - 確認根拠: evidence形式・coverage値・tests/failures/design_coverageに不足は見当たらない。
- [x] 証跡と実装レビューの不一致を報告へ反映した
  - 検証結果: 反映済み
  - 確認根拠: 証跡はpassだが実装・テスト未検出の指摘があるため、合否は不合格とする。
- [x] 完了可否へ証跡確認結果を反映した
  - 検証結果: 反映済み
  - 確認根拠: coverage門番は合格だが、実装品質指摘が残るため完了不可。

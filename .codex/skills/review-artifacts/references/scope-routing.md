# Scope Routing

ユーザ指定からレビュー種別を決める。複数に該当する場合は、該当する種別をすべて使う。

| ユーザ指定の例 | レビュー種別 | 使用する参照 |
| --- | --- | --- |
| `docs/`、要件定義、外部設計、内部設計、テスト方針、開発標準 | `documentation` | `documentation-review-checklist.md` |
| `src/`、実装、バックエンド、フロントエンド、設定読込、API実装 | `implementation` | `implementation-review-checklist.md` |
| `tests/`、単体テスト、結合テスト、総合テスト仕様、テストコード | `test` | `test-review-checklist.md` |
| `evidence/`、カバレッジ証跡、スクリーンショット、テスト結果、実行記録 | `evidence` | `evidence-review-checklist.md` |
| 仕様書と実装の照合、docs と src の乖離、設計とテストの整合 | `cross-artifact` | `cross-artifact-review-checklist.md` と対象に応じた複数の checklist を組み合わせる |
| 設定ファイル、README、CI、環境構築資材 | `cross-artifact` | `cross-artifact-review-checklist.md` と文書、実装、テスト、証跡のうち関係する checklist を組み合わせる |

## 曖昧な指定の扱い

- レビュー対象が広いが対象成果物の種類が明確な場合は、質問せず該当種別で進める。
- レビュー対象が不明で、読込範囲が大きく変わる場合だけユーザに 1 問確認する。
- `docs と src を照合` のように明示されている場合は、`cross-artifact`、`documentation`、`implementation` を組み合わせる。
- テスト仕様と証跡の照合が含まれる場合は、`test` と `evidence` を組み合わせる。

## 作成元スキルの推定

文書レビューでは、対象パスから作成元スキルを推定する。対応するスキルが存在しない場合は、対象文書の内容、周辺文書、ユーザ指示から近い作成基準を探す。

| 対象 | 作成元スキルの候補 |
| --- | --- |
| 要件定義 | `write-requirements-docs` |
| 外部設計 | `write-external-design-docs` |
| 内部設計 | `write-internal-design-docs` |
| 静的テスト方針 | `write-static-test-design-docs` |
| 単体テスト方針 | `write-unit-test-design-docs` |
| 結合テスト方針 | `write-integration-test-design-docs` |
| 総合テスト方針、総合テスト仕様・結果 | `write-system-test-design-docs` |
| 環境構築書 | `write-environment-setup-docs` |
| コーディング規約 | `write-coding-standards-docs` |
| 初期スキャフォールド | `scaffold-project-from-docs` |
| 実装、テスト、証跡更新 | `implement-from-docs` |

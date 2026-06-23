# Test Review Checklist round-1

## テスト方針との整合

- [x] テストコードとテスト仕様が、対応するテスト方針の範囲指定、テスト対象単位、除外範囲に一致しているか。
  - 検証結果: 指摘あり
  - 確認根拠: F001 の単体/結合テストは対象ディレクトリに配置され通常実行は通過するが、未解消 issue に対応する REST エラー形式、PathSecurity、trace_id、trace log retention、設定読込失敗ログ、coverage/evidence の確認が不足している。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_15-46-34_テスト証跡と分岐カバレッジが未確認.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-35_RESTエラー応答とtrace_id境界が設計と一致しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-36_PathSecurityServiceがWindows絶対パスを拒否しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-39_trace_id発番がUUIDv7設計に従っていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-40_トレースログ保持期間が実装で使われていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-41_設定読込失敗時にトレースログが保存されない.md`
- [x] テスト関連成果物のディレクトリ構成が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは `src/backend/tests/unit/`、結合テストは `src/backend/tests/integration/`、支援コードは `src/backend/tests/support/` に配置されている。
- [x] テスト関連成果物のファイル構成、ファイル名、配置先が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_config_loader.py`、`test_errors_and_tracing.py`、`test_database_models_contract.py`、`test_database_repository_contracts.py`、`test_backend_architecture_contract.py`、`test_app_config_api.py`、`test_database_migrations.py`、`test_trace_error_boundary.py` は F001 の設計単位別に分かれている。
- [x] 単体、結合、総合テストの役割が混ざっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは公開 contract と metadata/設定/エラー/Port を確認し、結合テストは ASGI、PostgreSQL migration、trace log ファイル境界を確認している。総合テストの画面実機確認は含めていない。
- [x] テスト方針で求める観点、カバレッジ、証跡、実行環境、完了条件が満たされているか。
  - 検証結果: 指摘あり
  - 確認根拠: `pytest src/backend/tests/unit -q` は 41 passed、`pytest src/backend/tests/integration -q` は 9 passed だが、`docs/04_テスト/.../evidence/` の分岐カバレッジ証跡が存在しない。`ruff format --check src/backend` も不合格。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_15-46-33_ruff_format_checkが不合格.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-34_テスト証跡と分岐カバレッジが未確認.md`
- [x] テスト方針が実装や設計の現状に追従していない場合は、テスト方針側を直す方針を書く。
  - 検証結果: 指摘なし
  - 確認根拠: テスト方針の分岐カバレッジ、証跡、配置、実行環境の定義が古いとは判断できず、現状は成果物側の未達として扱う。

## 単体テスト

- [x] 公開関数、公開メソッド、コンポーネント、純粋ロジックの責務を単位としているか。
  - 検証結果: 指摘なし
  - 確認根拠: `ConfigLoader.load`、`AppError`、`new_trace_id`、SQLAlchemy metadata、Repository Port、architecture import contract など公開境界を単位にしている。
- [x] 外部副作用を Fake、Stub、Mock、fixture で差し替えているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは `tmp_path` とテスト支援 fixture を使い、実DB、実HTTP、実Codex、実ブラウザを起動していない。
- [x] 事前条件、事後条件、不変条件、正常系、異常系、境界値、分岐が確認されているか。
  - 検証結果: 指摘あり
  - 確認根拠: 設定必須項目や DB 制約は確認されているが、Windows 絶対パス拒否、UUIDv7 trace_id、trace_log retention、設定読込失敗時ログなどの境界が未確認で、対応実装も未達。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_15-46-36_PathSecurityServiceがWindows絶対パスを拒否しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-39_trace_id発番がUUIDv7設計に従っていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-40_トレースログ保持期間が実装で使われていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-41_設定読込失敗時にトレースログが保存されない.md`
- [x] テストが内部実装詳細に密結合しすぎていないか。
  - 検証結果: 指摘なし
  - 確認根拠: テストは YAML 入力と公開例外、ORM metadata contract、DB inspect 結果、HTTP 応答、trace log YAML を観測しており、内部関数の呼び出し順だけを固定していない。
- [x] テストが単に例外が出ないことではなく、仕様上意味のある結果、状態変化、副作用、出力を検証しているか。
  - 検証結果: 指摘あり
  - 確認根拠: 正常/異常の値検証は多いが、REST エラー応答の必須 `error` と共通形式、入口 trace_id 生成を検証できていない。
  - 指摘: `.issue/implement-from-docs/2026-06-21_15-46-35_RESTエラー応答とtrace_id境界が設計と一致しない.md`

## 結合テスト

- [x] 外部インターフェース、処理設計、永続化、ファイル、通信境界、表示または操作連携を設計単位で確認しているか。
  - 検証結果: 指摘あり
  - 確認根拠: app-config、migration、trace boundary の結合テストは存在するが、REST エラー応答形式、設定読込失敗時の app_bootstrap_failed ログ、trace log retention の起動時処理は設計単位として未確認である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_15-46-35_RESTエラー応答とtrace_id境界が設計と一致しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-40_トレースログ保持期間が実装で使われていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-41_設定読込失敗時にトレースログが保存されない.md`
- [x] 実外部サービス、実行環境、実行時間や環境差分が大きい対象を不必要に使っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは ASGITransport、PostgreSQL test DB、ローカル一時ファイルに限定され、実Codex、実ブラウザ、外部ネットワークを使っていない。検証役環境でも PostgreSQL 接続は成功した。
- [x] Mock、Fake、Stub が過剰で、実際の契約違反や結合不備を隠していないか。
  - 検証結果: 指摘なし
  - 確認根拠: migration は実 PostgreSQL へ適用し、app-config と trace boundary は FastAPI ASGI 境界で確認している。認証依存関係の override は app-config の保護対象 API 前提を固定するための範囲にとどまる。
- [x] トランザクション、状態更新、競合、ロールバック、エラー変換、ログ依頼が確認されているか。
  - 検証結果: 指摘あり
  - 確認根拠: DB 制約と trace log 書込は一部確認されているが、FastAPI 標準 `HTTPException` の共通エラー変換、設定読込失敗ログ、retention 削除は未達である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_15-46-35_RESTエラー応答とtrace_id境界が設計と一致しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-40_トレースログ保持期間が実装で使われていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-41_設定読込失敗時にトレースログが保存されない.md`
- [x] テストデータが独立し、実行順序に依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: `prepare_foundation_database` は public schema を初期化してから migration を適用し、HTTP/trace tests は `tmp_path` 配下へ設定とログを作るため、実行順序に依存しない。
- [x] 時刻、乱数、実行順序、外部通信、ファイルシステム、DB 状態により不安定になるテストになっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 検証役環境で integration は `9 passed` となり、PostgreSQL `127.0.0.1:55432` 接続不能の環境差分は発生しなかった。ファイル出力は `tmp_path`、DB は初期化 fixture を使う。
- [x] テストデータが実装ロジックのコピーや都合のよい値だけになっておらず、境界値、異常値、業務上意味のある値を含んでいるか。
  - 検証結果: 指摘なし
  - 確認根拠: 必須設定欠落、正数制約違反、timezone 不正、DB 制約違反、未完了 run 重複、予期しない API 例外などの異常値を含む。

## 総合テスト

- [x] 利用者が利用者インターフェースまたは実運用に近い経路で業務を完了できることを確認しているか。
  - 検証結果: 対象外
  - 理由: 今回は F001 の結合テスト完了検証と実装品質レビューであり、機能別総合テストは state.md 上も未実施工程。
- [x] 自動確認、手動確認、通信確認、永続化確認、ファイル確認の役割がテスト方針と一致しているか。
  - 検証結果: 対象外
  - 理由: 総合テスト仕様・結果と画面証跡は今回のレビュー対象外。
- [x] 未実施、一部確認、保留、不合格、再テストの記録がテスト仕様・結果に残っているか。
  - 検証結果: 対象外
  - 理由: F001 の機能別総合テストはまだ実施前で、総合テスト結果記録を判定する段階ではない。
- [x] 実行証跡とテストケースが追跡できるか。
  - 検証結果: 対象外
  - 理由: ここでは単体/結合/evidence の品質ゲートを確認しており、総合テストケース別証跡は対象外。

## TDD と実装順序

- [x] 実装成果物レビューでは、TDD が要求される範囲で Red、Green、Refactor の証跡または説明があるか。
  - 検証結果: 指摘なし
  - 確認根拠: state.md に実装依頼時点の Red、生成役の Green 結果、実装修正 round-2 の再確認結果が記録されている。
- [x] Red を事後的に作れない場合は、レビュー指摘として記録し、今後の修正方針を示す。
  - 検証結果: 指摘なし
  - 確認根拠: Red は F001 本実装未作成/未完成から始まった経緯が state.md に残っており、事後作成不能とは判断しない。
- [x] テスト追加が不要な場合は、除外理由が方針と整合しているか。
  - 検証結果: 対象外
  - 理由: 未解消 issue が残っており、テスト追加不要の判断段階ではない。

## 不要なコメントと作業経緯

- [x] テスト名、docstring、コメント、テスト仕様、証跡に、確認対象の理解や再実行に不要な作業経緯、内部事情、言い訳、暫定理由が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象テストの docstring は `観点` と `確認` を中心にした日本語記述で、レビュー対応理由や環境都合は本文へ混入していない。
- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 指摘なし
  - 確認根拠: 設定読込 IF、Repository 境界、DB 制約、REST 境界、trace log 境界の確認意図が記述されている。
- [x] テスト失敗理由、作成時の都合、環境制約、ツール制約、レビュー指摘への反応など、成果物ではなく作業報告や issue に書くべき内容が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: PostgreSQL 接続差分や生成役報告は state.md に記録され、テスト本文には書かれていない。
- [x] `既存実装があるので失敗しない`、`一旦この実装にしている`、`あとで修正する`、`指摘されたため追加`、`カバレッジのため追加`、`環境の都合で確認できない`、`旧仕様ではこうだった`、コードの単なる日本語言い換えなどが残っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: `rg` で対象語句を確認し、テスト本文に該当する暫定・経緯文言は見つからなかった。
- [x] 業務ルール上の非自明な前提、セキュリティ上の制約、外部仕様に由来する制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行、時刻、ID、ファイル、通信の注意点など、確認や保守に必要な説明は残されているか。
  - 検証結果: 指摘なし
  - 確認根拠: Cookie 前提、内部設定非公開、DB 初期化、Alembic 管理テーブル許容、trace log YAML 必須項目など、保守に必要な前提はテスト名と docstring から追跡できる。

## 修正方針の判断

- [x] テスト不足ならテストコード、テスト仕様、証跡のどれを補うかを書く。
  - 検証結果: 指摘あり
  - 確認根拠: coverage/evidence の不足は証跡追加、未解消実装 issue は実装修正と対応テスト追加が必要。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_15-46-34_テスト証跡と分岐カバレッジが未確認.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-35_RESTエラー応答とtrace_id境界が設計と一致しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-36_PathSecurityServiceがWindows絶対パスを拒否しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-39_trace_id発番がUUIDv7設計に従っていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-40_トレースログ保持期間が実装で使われていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-41_設定読込失敗時にトレースログが保存されない.md`
- [x] テストが仕様に従っていて実装が違う場合は、実装側を直す方針を書く。
  - 検証結果: 指摘あり
  - 確認根拠: RESTエラー、PathSecurity、Alembic、trace_id、trace log retention、設定読込失敗ログは、仕様に対して実装が未達である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_15-46-35_RESTエラー応答とtrace_id境界が設計と一致しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-36_PathSecurityServiceがWindows絶対パスを拒否しない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-37_AlembicリビジョンがORM現在形に依存している.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-39_trace_id発番がUUIDv7設計に従っていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-40_トレースログ保持期間が実装で使われていない.md`
    - `.issue/implement-from-docs/2026-06-21_15-46-41_設定読込失敗時にトレースログが保存されない.md`
- [x] テスト方針が過剰または古い場合は、テスト方針と関連成果物を直す方針を書く。
  - 検証結果: 指摘なし
  - 確認根拠: テスト方針の分岐カバレッジと証跡要件を過剰または古いと判断する根拠はない。

## test 集計

- checklist 総項目数: 33
- checklist 処理済み項目数: 33
- checklist 未処理項目数: 0
- checklist 指摘あり件数: 8
- checklist 対象外件数: 5
- checklist 判断不能件数: 0
- 根拠なし `- [x]`: なし

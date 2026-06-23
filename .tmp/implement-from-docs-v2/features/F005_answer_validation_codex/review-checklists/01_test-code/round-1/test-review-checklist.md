# Test Review Checklist

## テスト方針との整合

- [x] テストコードとテスト仕様が、対応するテスト方針の範囲指定、テスト対象単位、除外範囲に一致しているか。
  - 検証結果: 指摘あり
  - 確認根拠: F005 のテストは JSONL parser、Port DTO、回答検証、採用成果物保存、ExecuteChatRun 連携、Fake Codex による DB/REST/SSE 再表示を対象にしており、概ね単体・結合テスト方針の範囲に沿う。一方で単体テスト方針と詳細設計で対象となる `CodexRunner`、`CodexWorkspacePreparer`、`turn.completed`、回答固定検証の一部異常系が未検証である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-07_F005_JSONL完了イベントの契約テストが不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-08_F005_回答固定検証の異常系テストが不足.md`
- [x] テスト関連成果物のディレクトリ構成が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: F005 の単体テストは `src/backend/tests/unit/infrastructure/codex/`、`src/backend/tests/unit/application/validation/`、`src/backend/tests/unit/application/artifacts/`、`src/backend/tests/unit/application/execution/`、`src/backend/tests/unit/application/ports/` に配置され、結合テストは `src/backend/tests/integration/`、補助は `src/backend/tests/support/codex.py` に配置されている。
- [x] テスト関連成果物のファイル構成、ファイル名、配置先が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘あり
  - 確認根拠: 追加ファイル名と配置先は既存構成に沿うが、詳細設計対象の `CodexRunner` と `CodexWorkspacePreparer` に対応する単体テストファイルが存在しない。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
- [x] 単体、結合、総合テストの役割が混ざっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは fake/stub で application と infrastructure の公開契約を確認し、結合テストは実 DB と FastAPI 経由の履歴詳細/SSE 再表示を確認している。総合テスト仕様や Playwright 固定テストは作成されていない。
- [x] テスト方針で求める観点、カバレッジ、証跡、実行環境、完了条件が満たされているか。
  - 検証結果: 指摘あり
  - 確認根拠: 生成役報告上、ruff と Red 確認は記録されているが、単体テスト方針が明示する JSONL の `turn.completed`、インフラ層の外部副作用境界、回答検証の固定検証異常系が不足している。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-07_F005_JSONL完了イベントの契約テストが不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-08_F005_回答固定検証の異常系テストが不足.md`
- [x] テスト方針が実装や設計の現状に追従していない場合は、テスト方針側を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: テスト方針が古いのではなく、現テストコード側の網羅不足として判断した。
  - 理由: テスト方針側の修正指摘ではないため。

## 単体テスト

- [x] 公開関数、公開メソッド、コンポーネント、純粋ロジックの責務を単位としているか。
  - 検証結果: 指摘あり
  - 確認根拠: `JsonlEventParser`、`ValidateAnswerUseCase`、`SaveAdoptedArtifactsUseCase`、`ExecuteChatRunUseCase` は公開責務単位でテストされている。一方で `CodexRunner` の `run_generation` / `run_validation` / `cancel`、`CodexWorkspacePreparer` の公開関数単位のテストがない。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
- [x] 外部副作用を Fake、Stub、Mock、fixture で差し替えているか。
  - 検証結果: 指摘あり
  - 確認根拠: application 側では fake runner、fake validator、fake artifact store、fake repository により副作用が差し替えられている。しかし Codex Docker 起動と workspace 準備のインフラ単体テストがないため、外部副作用境界を fake/stub で差し替えて依頼内容を検証する観点が不足している。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
- [x] 事前条件、事後条件、不変条件、正常系、異常系、境界値、分岐が確認されているか。
  - 検証結果: 指摘あり
  - 確認根拠: 再生成上限、timeout、PDF読込不能、成果物保存不正、生成失敗は確認されている。一方で `turn.completed`、CodexRunner の Docker 引数・timeout・cancel 分類、WorkspacePreparer の作業領域事後条件、空回答・非PDF・危険HTML・成果物固定検証異常系が未確認である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-07_F005_JSONL完了イベントの契約テストが不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-08_F005_回答固定検証の異常系テストが不足.md`
- [x] テストが内部実装詳細に密結合しすぎていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 既存の F005 テストは UseCase command/result、Port DTO、parser の公開イベント、DB/REST/SSE の外部観測結果を検証しており、private メソッドや実装内部の一時変数を固定していない。
- [x] テストが単に例外が出ないことではなく、仕様上意味のある結果、状態変化、副作用、出力を検証しているか。
  - 検証結果: 指摘あり
  - 確認根拠: 既存テストは run state、intermediate messages、answer 保存、artifact URL 置換、trace、DB 再表示を具体的に assert している。ただし JSONL 完了イベントと固定検証異常系は仕様上意味のある出力・分岐を未検証である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-22_07-00-07_F005_JSONL完了イベントの契約テストが不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-08_F005_回答固定検証の異常系テストが不足.md`

## 結合テスト

- [x] 外部インターフェース、処理設計、永続化、ファイル、通信境界、表示または操作連携を設計単位で確認しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_codex_execution_answer_persistence.py` は Fake Codex 応答から `ExecuteChatRunUseCase`、DB 保存、履歴詳細 API、SSE answer payload までを確認し、検証失敗上限時に answer/artifact が保存されないことも確認している。
- [x] 実外部サービス、実行環境、実行時間や環境差分が大きい対象を不必要に使っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは実 Codex を起動せず、Fake 応答で上位連携を確認している。生成役報告でも結合テストは承認付き DB 接続のみで、実 Codex は起動していない。
- [x] Mock、Fake、Stub が過剰で、実際の契約違反や結合不備を隠していないか。
  - 検証結果: 指摘あり
  - 確認根拠: F005 結合テストで実 Codex を起動しない方針自体は妥当だが、その代替として必要な `CodexRunner` / `CodexWorkspacePreparer` の単体契約が不足しているため、Docker 実行境界の契約違反を隠すリスクが残る。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
- [x] トランザクション、状態更新、競合、ロールバック、エラー変換、ログ依頼が確認されているか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは run が `completed` または `error` へ終端すること、回答と成果物の保存有無、履歴詳細 API での `answer` 有無を検証している。単体側でも生成失敗時の trace stage と error 終端を確認している。
- [x] テストデータが独立し、実行順序に依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは `prepare_foundation_database()`、`seed_chat_user()`、`insert_chat_run()` でテストごとに DB を準備し、セッション token もケースごとに分けている。
- [x] 時刻、乱数、実行順序、外部通信、ファイルシステム、DB 状態により不安定になるテストになっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体は `FixedClock` と fake を使用し、結合は PostgreSQL 以外の外部 Codex 実行を避けている。成果物候補は `tmp_path` 配下で作成される。
- [x] テストデータが実装ロジックのコピーや都合のよい値だけになっておらず、境界値、異常値、業務上意味のある値を含んでいるか。
  - 検証結果: 指摘あり
  - 確認根拠: 再生成、timeout、検証失敗、参照元不正、成果物不正はあるが、回答固定検証で設計が求める空回答、非PDF、危険HTML、成果物リンク不備を `ValidateAnswerUseCase` の異常値として確認していない。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-00-08_F005_回答固定検証の異常系テストが不足.md`

## 総合テスト

- [x] 利用者が利用者インターフェースまたは実運用に近い経路で業務を完了できることを確認しているか。
  - 検証結果: 対象外
  - 確認根拠: 現在フェーズは単体・結合テストコードレビューであり、機能別総合テストや正式総合テストは対象外である。
  - 理由: 総合テストレビューではないため。
- [x] 自動確認、手動確認、通信確認、永続化確認、ファイル確認の役割がテスト方針と一致しているか。
  - 検証結果: 対象外
  - 確認根拠: F005 テストコード先行作成フェーズでは総合テストの自動/手動分類や証跡記録を扱わない。
  - 理由: 総合テスト成果物がレビュー対象に含まれないため。
- [x] 未実施、一部確認、保留、不合格、再テストの記録がテスト仕様・結果に残っているか。
  - 検証結果: 対象外
  - 確認根拠: `docs/04_テスト/04_総合テスト/` の結果記録は今回対象外であり、F005 の機能別総合テストは未実施フェーズである。
  - 理由: 総合テスト仕様・結果レビューではないため。
- [x] 実行証跡とテストケースが追跡できるか。
  - 検証結果: 対象外
  - 確認根拠: 今回はテストコードレビューであり、coverage/evidence や総合テスト証跡の追跡性は後続フェーズで確認する。
  - 理由: 証跡レビューではないため。

## TDD と実装順序

- [x] 実装成果物レビューでは、TDD が要求される範囲で Red、Green、Refactor の証跡または説明があるか。
  - 検証結果: 指摘なし
  - 確認根拠: state と生成役報告に、ruff pass、unit `21 failed, 144 passed`、integration `2 failed, 83 passed`、失敗理由が F005 未実装の `ModuleNotFoundError` であることが記録されている。
- [x] Red を事後的に作れない場合は、レビュー指摘として記録し、今後の修正方針を示す。
  - 検証結果: 対象外
  - 確認根拠: Red は成立しており、Red を事後的に作れないケースではない。
  - 理由: Red 不能の状況ではないため。
- [x] テスト追加が不要な場合は、除外理由が方針と整合しているか。
  - 検証結果: 対象外
  - 確認根拠: 今回はテスト追加不要ではなく、追加すべき不足を issue 化している。
  - 理由: テスト追加不要判断ではないため。

## 不要なコメントと作業経緯

- [x] テスト名、docstring、コメント、テスト仕様、証跡に、確認対象の理解や再実行に不要な作業経緯、内部事情、言い訳、暫定理由が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象テスト本文を確認し、Red 理由、レビュー対応、暫定対応、カバレッジ目的などの作業経緯コメントは確認していない。
- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 指摘なし
  - 確認根拠: 各テスト docstring は `観点：` と `確認：` で契約と期待結果を説明しており、単体テスト方針の形式に沿っている。
- [x] テスト失敗理由、作成時の都合、環境制約、ツール制約、レビュー指摘への反応など、成果物ではなく作業報告や issue に書くべき内容が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: Red 理由は state と生成役報告にあり、テスト本文・docstring・補助ファイルには混入していない。
- [x] `既存実装があるので失敗しない`、`一旦この実装にしている`、`あとで修正する`、`指摘されたため追加`、`カバレッジのため追加`、`環境の都合で確認できない`、`旧仕様ではこうだった`、コードの単なる日本語言い換えなどが残っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: `rg` と本文確認で、該当する暫定表現や旧仕様説明は確認していない。
- [x] 業務ルール上の非自明な前提、セキュリティ上の制約、外部仕様に由来する制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行、時刻、ID、ファイル、通信の注意点など、確認や保守に必要な説明は残されているか。
  - 検証結果: 指摘なし
  - 確認根拠: fake は Protocol/dataclass で観測項目を明示し、実 Codex を起動しない結合テストも docstring で Fake 応答による確認範囲を説明している。

## 修正方針の判断

- [x] テスト不足ならテストコード、テスト仕様、証跡のどれを補うかを書く。
  - 検証結果: 指摘あり
  - 確認根拠: 不足は F005 テストコードの網羅不足であり、`CodexRunner` / `CodexWorkspacePreparer`、JSONL `turn.completed`、回答固定検証異常系のテスト追加が必要である。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-22_07-00-06_F005_CodexRunnerとWorkspacePreparerの単体契約が不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-07_F005_JSONL完了イベントの契約テストが不足.md`
    - `.issue/implement-from-docs/2026-06-22_07-00-08_F005_回答固定検証の異常系テストが不足.md`
- [x] テストが仕様に従っていて実装が違う場合は、実装側を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: F005 本実装は未作成であり、今回の指摘は実装差異ではなくテストコード不足である。
  - 理由: 実装修正方針を判定するフェーズではないため。
- [x] テスト方針が過剰または古い場合は、テスト方針と関連成果物を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: テスト方針や設計書が過剰または古いのではなく、現テストが設計観点を満たしていない。
  - 理由: テスト方針修正ではなくテストコード修正が必要なため。

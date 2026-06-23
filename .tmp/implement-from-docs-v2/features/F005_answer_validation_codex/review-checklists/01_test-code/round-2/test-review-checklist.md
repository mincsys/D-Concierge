# Test Review Checklist

## テスト方針との整合

- [x] テストコードとテスト仕様が、対応するテスト方針の範囲指定、テスト対象単位、除外範囲に一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `docs/04_テスト/02_単体テスト/単体テスト方針.md` の JSONL 解析、回答検証、パス安全性、実行制御、CodexRunner 差し替え観点と、`src/backend/tests/unit/infrastructure/codex/test_codex_runner_and_workspace.py`、`test_jsonl_event_parser.py`、`test_validate_answer_use_case.py`、`test_execute_chat_run_use_case.py` を照合した。結合テストは `docs/04_テスト/03_結合テスト/結合テスト方針.md` の実 Codex 不使用方針どおり `FakeCodexGenerationRunner` / `FakeValidatorCodexRunner` で API/DB/SSE 再表示を確認している。
- [x] テスト関連成果物のディレクトリ構成が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: F005 の単体テストは `src/backend/tests/unit/infrastructure/codex/`、`src/backend/tests/unit/application/validation/`、`src/backend/tests/unit/application/artifacts/`、`src/backend/tests/unit/application/execution/`、port 契約は `src/backend/tests/unit/application/ports/`、結合テストは `src/backend/tests/integration/` に配置され、方針書の backend 単体・結合テスト配置と一致している。
- [x] テスト関連成果物のファイル構成、ファイル名、配置先が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_codex_runner_and_workspace.py`、`test_jsonl_event_parser.py`、`test_validate_answer_use_case.py`、`test_save_adopted_artifacts_use_case.py`、`test_execute_chat_run_use_case.py`、`test_codex_execution_answer_persistence.py` は、設計上の `CodexRunner`、`JsonlEventParser`、`ValidateAnswerUseCase`、`SaveAdoptedArtifactsUseCase`、`ExecuteChatRunUseCase`、結合境界に対応する単位で分かれている。
- [x] 単体、結合、総合テストの役割が混ざっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは Fake/Stub と `tmp_path` で副作用を局所化し、結合テスト `test_codex_execution_answer_persistence.py` は PostgreSQL、FastAPI app、DB repository、履歴詳細 API、SSE payload を対象にしている。総合テスト仕様や画面操作の記録は今回の F005 テストコードには含まれていない。
- [x] テスト方針で求める観点、カバレッジ、証跡、実行環境、完了条件が満たされているか。
  - 検証結果: 指摘あり
  - 確認根拠: JSONL `turn.completed`、CodexRunner/WorkspacePreparer、固定検証異常系は round-2 修正で追加されている。一方、`docs/04_テスト/02_単体テスト/単体テスト方針.md` が求めるトレースログ観点と `ExecuteChatRunUseCaseクラス設計.md` のエラートレース契約に対し、`test_execute_chat_run_use_case.py` は生成失敗以外の検証上限超過、PDF 読込失敗、タイムアウト、採用保存失敗の trace 依頼を確認していない。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-15-01_F005_実行ユースケースのエラートレース契約テストが不足.md`
- [x] テスト方針が実装や設計の現状に追従していない場合は、テスト方針側を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 今回確認した不足はテスト方針の過剰・陳腐化ではなく、`ExecuteChatRunUseCase` の設計とテスト方針に対するテストコード不足である。
  - 理由: テスト方針側の修正ではなく、F005 テストコード側の補強が必要なため。

## 単体テスト

- [x] 公開関数、公開メソッド、コンポーネント、純粋ロジックの責務を単位としているか。
  - 検証結果: 指摘なし
  - 確認根拠: `CodexWorkspacePreparer` の公開関数、`CodexRunner.run_generation` / `run_validation` / `cancel`、`JsonlEventParser.parse_line`、`ValidateAnswerUseCase.execute`、`SaveAdoptedArtifactsUseCase.execute`、`ExecuteChatRunUseCase.execute`、port DTO の公開契約を単位としてテストが構成されている。
- [x] 外部副作用を Fake、Stub、Mock、fixture で差し替えているか。
  - 検証結果: 指摘なし
  - 確認根拠: Docker 実行は `RecordingCodexProcessRunner` と `RecordingDockerStopper`、生成・検証 Codex は `FakeCodexGenerationRunner` と `FakeValidatorCodexRunner`、PDF 参照元は `FakeReferenceFileValidator`、成果物保存は `FakeAdoptedArtifactStore`、DB/時計/イベント/trace は専用 fake で差し替えられている。
- [x] 事前条件、事後条件、不変条件、正常系、異常系、境界値、分岐が確認されているか。
  - 検証結果: 指摘あり
  - 確認根拠: round-2 で追加された `test_codex_runner_and_workspace.py` は作業領域作成、準備失敗、生成/検証 Docker 引数、timeout、cancel 分類を確認している。`test_jsonl_event_parser.py` は `turn.completed` と開始系内部イベントを確認している。`test_validate_answer_use_case.py` は空回答、非 PDF、危険 HTML、成果物リンク不正を Codex 検証前に遮断する。一方、`ExecuteChatRunUseCase` の検証上限超過、PDF 読込失敗、timeout、採用保存失敗の trace 境界は未確認である。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-15-01_F005_実行ユースケースのエラートレース契約テストが不足.md`
- [x] テストが内部実装詳細に密結合しすぎていないか。
  - 検証結果: 指摘なし
  - 確認根拠: `CodexRunner` は設計上の subprocess 境界へ渡す名前付き引数と cancel 分類を観測し、`JsonlEventParser` は公開イベント種別と payload 抽出結果を確認している。`ValidateAnswerUseCase` と `ExecuteChatRunUseCase` は公開 command/result と port fake の観測記録を使っており、private 関数や一時変数名には依存していない。
- [x] テストが単に例外が出ないことではなく、仕様上意味のある結果、状態変化、副作用、出力を検証しているか。
  - 検証結果: 指摘あり
  - 確認根拠: 多くのテストは状態遷移、DB 保存、SSE payload、成果物 URL 置換、再生成指示、Docker 引数、エラー分類を assert している。ただし `ExecuteChatRunUseCase` の複数の異常終端について、仕様上意味のある副作用である trace 依頼を検証していない。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-15-01_F005_実行ユースケースのエラートレース契約テストが不足.md`

## 結合テスト

- [x] 外部インターフェース、処理設計、永続化、ファイル、通信境界、表示または操作連携を設計単位で確認しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_codex_execution_answer_persistence.py` は Fake Codex 実行から `ExecuteChatRunUseCase`、DB repository、履歴詳細 API、SSE answer payload までを確認し、completed 時の回答本文、参照元 locator、保存済み成果物 URL、検証失敗時の error と answer 非保存を確認している。
- [x] 実外部サービス、実行環境、実行時間や環境差分が大きい対象を不必要に使っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは `FakeCodexGenerationRunner`、`FakeValidatorCodexRunner`、`FakeReferenceFileValidator`、`FakeAdoptedArtifactStore` を使い、`docs/04_テスト/03_結合テスト/結合テスト方針.md` の「実 Codex は起動しない」方針に従っている。
- [x] Mock、Fake、Stub が過剰で、実際の契約違反や結合不備を隠していないか。
  - 検証結果: 指摘なし
  - 確認根拠: Codex とファイル保存の外部境界だけを fake 化し、DB repository、transaction manager、FastAPI app、履歴詳細 API、SSE parser は実経路で確認しているため、F005 の結合契約を隠す過剰 fake にはなっていない。
- [x] トランザクション、状態更新、競合、ロールバック、エラー変換、ログ依頼が確認されているか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストでは completed/error の DB 状態、回答ブロック数、成果物保存パス、履歴詳細 API の answer 有無を確認している。ログ依頼不足は単体の `ExecuteChatRunUseCase` trace 契約不足として別項目で issue 化済みであり、結合テスト単独に実 trace store を要求する設計ではない。
- [x] テストデータが独立し、実行順序に依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは各ケースで `prepare_foundation_database(database_url)`、`seed_chat_user`、`insert_chat_run` を使って DB 状態を作り直し、セッション token もケースごとに分けている。
- [x] 時刻、乱数、実行順序、外部通信、ファイルシステム、DB 状態により不安定になるテストになっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは `tmp_path`、固定 UUID、`FixedClock`、fake runner を使い、結合テストも実 Codex や外部通信を起動せず、DB はテスト用 database URL を準備してから実行する構成になっている。
- [x] テストデータが実装ロジックのコピーや都合のよい値だけになっておらず、境界値、異常値、業務上意味のある値を含んでいるか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_validate_answer_use_case.py` は空回答、非 PDF、危険 HTML、親ディレクトリ、絶対パス、URL、許可外拡張子、存在しない成果物を含み、`test_codex_runner_and_workspace.py` は resume あり/なし、timeout、stop 失敗、未登録、終了済みを含む。結合テストも成功保存と検証失敗を分けている。

## 総合テスト

- [x] 利用者が利用者インターフェースまたは実運用に近い経路で業務を完了できることを確認しているか。
  - 検証結果: 対象外
  - 確認根拠: 今回のフェーズは F005 テストコード再レビューであり、機能別総合テストや正式総合テストの実施結果はレビュー対象に含まれていない。
  - 理由: 総合テストレビューのフェーズではないため。
- [x] 自動確認、手動確認、通信確認、永続化確認、ファイル確認の役割がテスト方針と一致しているか。
  - 検証結果: 対象外
  - 確認根拠: F005 の機能別総合テスト仕様・結果や evidence は今回のレビュー対象ではなく、単体・結合テストコードの役割分担を確認した。
  - 理由: 総合テスト成果物の確認フェーズではないため。
- [x] 未実施、一部確認、保留、不合格、再テストの記録がテスト仕様・結果に残っているか。
  - 検証結果: 対象外
  - 確認根拠: `docs/04_テスト/04_総合テスト/` または `.tmp` 側 system-test 結果は F005 テストコードレビューの対象外である。
  - 理由: 総合テスト仕様・結果を更新・確認する段階ではないため。
- [x] 実行証跡とテストケースが追跡できるか。
  - 検証結果: 対象外
  - 確認根拠: テストコード先行レビューでは生成役の Red 実行結果要約を state で確認する段階であり、coverage evidence や総合テスト証跡はまだ対象ではない。
  - 理由: 証跡レビューのフェーズではないため。

## TDD と実装順序

- [x] 実装成果物レビューでは、TDD が要求される範囲で Red、Green、Refactor の証跡または説明があるか。
  - 検証結果: 指摘なし
  - 確認根拠: `state.md` の Red 確認結果と生成役報告に、round-2 修正後の `ruff check src/backend/tests` pass、単体 `40 failed, 144 passed`、結合 `2 failed, 83 passed`、失敗理由が F005 未実装 `ModuleNotFoundError` であることが記録されている。今回フェーズは実装前のテストコードレビューであるため Green/Refactor は未要求である。
- [x] Red を事後的に作れない場合は、レビュー指摘として記録し、今後の修正方針を示す。
  - 検証結果: 対象外
  - 確認根拠: 生成役報告と `state.md` では F005 本実装未作成に起因する Red が成立しており、Red を作れない状況ではない。
  - 理由: Red 不成立ではないため。
- [x] テスト追加が不要な場合は、除外理由が方針と整合しているか。
  - 検証結果: 対象外
  - 確認根拠: 今回は F005 テストコード先行作成および修正後再レビューであり、テスト追加不要の判断は行われていない。
  - 理由: テスト追加不要のケースではないため。

## 不要なコメントと作業経緯

- [x] テスト名、docstring、コメント、テスト仕様、証跡に、確認対象の理解や再実行に不要な作業経緯、内部事情、言い訳、暫定理由が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象 F005 テスト群と `src/backend/tests/support/codex.py` を `Red`、`ModuleNotFound`、`指摘`、`暫定`、`あとで`、`一旦`、`カバレッジ` などで確認し、作業経緯やレビュー反応の混入は見つからなかった。
- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 指摘なし
  - 確認根拠: 各テストの docstring は「観点」「確認」の形式で、Docker 起動境界、JSONL イベント、固定検証、成果物保存、DB/SSE 再表示など、仕様上の契約と確認内容を説明している。
- [x] テスト失敗理由、作成時の都合、環境制約、ツール制約、レビュー指摘への反応など、成果物ではなく作業報告や issue に書くべき内容が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: Red 理由や F005 未実装理由は `state.md` と生成役報告に記録され、テスト本文には `ModuleNotFoundError` やレビュー指摘への反応を示す記載はない。
- [x] `既存実装があるので失敗しない`、`一旦この実装にしている`、`あとで修正する`、`指摘されたため追加`、`カバレッジのため追加`、`環境の都合で確認できない`、`旧仕様ではこうだった`、コードの単なる日本語言い換えなどが残っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象テスト群の docstring とコメントを確認し、暫定表現、旧仕様の痕跡、レビュー対応の説明、環境制約の言い訳は含まれていない。
- [x] 業務ルール上の非自明な前提、セキュリティ上の制約、外部仕様に由来する制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行、時刻、ID、ファイル、通信の注意点など、確認や保守に必要な説明は残されているか。
  - 検証結果: 指摘なし
  - 確認根拠: `CodexRunnerLike`、`GenerationRequestLike`、`ValidationRequestLike`、`ArtifactSourceLike` などの Protocol には観測対象境界が説明され、テスト docstring も `--host-artifacts`、`turn.completed`、固定検証、実 Codex 不使用、保存済み URL 置換などの非自明な契約を示している。

## 修正方針の判断

- [x] テスト不足ならテストコード、テスト仕様、証跡のどれを補うかを書く。
  - 検証結果: 指摘あり
  - 確認根拠: 不足しているのは F005 テストコードの `ExecuteChatRunUseCase` 異常系 trace 契約であり、総合テスト仕様や証跡ではなく単体テスト補強が主な修正先である。指摘ファイルに修正方針を記録した。
  - 指摘: `.issue/implement-from-docs/2026-06-22_07-15-01_F005_実行ユースケースのエラートレース契約テストが不足.md`
- [x] テストが仕様に従っていて実装が違う場合は、実装側を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 今回は F005 本実装前のテストコードレビューであり、実装とテストの不一致は確認対象ではない。指摘はテスト不足として扱う。
  - 理由: 実装差異ではなくテストコード不足のため。
- [x] テスト方針が過剰または古い場合は、テスト方針と関連成果物を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: テスト方針と設計は F005 の trace、JSONL、固定検証、Codex fake 境界を明示しており、過剰または古い方針とは判断していない。
  - 理由: テスト方針側の修正対象ではないため。

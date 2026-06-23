# Test Review Checklist

レビュー対象: F004 実行状態・SSE・キャンセル・起動時実行回復 テストコードレビュー round-2
レビュー日: 2026-06-22

## テスト方針との整合

- [x] テストコードとテスト仕様が、対応するテスト方針の範囲指定、テスト対象単位、除外範囲に一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テスト方針は backend 単体を `src/backend/tests/unit/`、結合テスト方針は backend REST/SSE API と起動時実行回復を `src/backend/tests/integration/` で扱うと定義している。F004 対象は `src/backend/tests/unit/application/execution/`、`src/backend/tests/unit/application/ports/test_chat_port_contracts.py`、`src/backend/tests/integration/test_execution_sse_cancel_api.py`、`src/backend/tests/support/execution.py` に配置され、F004 の SSE、キャンセル、起動時回復の範囲に収まっている。
- [x] テスト関連成果物のディレクトリ構成が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_cancel_and_recovery_use_cases.py` と `test_sse_event_broker.py` は application execution 単体、`test_chat_port_contracts.py` は Port 契約、`test_execution_sse_cancel_api.py` は API/DB 結合、`tests/support/execution.py` はテスト支援コードであり、単体/結合テスト方針の配置規則と一致する。
- [x] テスト関連成果物のファイル構成、ファイル名、配置先が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 処理設計のキャンセル、SSE、起動時回復に対応して `test_cancel_and_recovery_use_cases.py`、`test_sse_event_broker.py`、`test_execution_sse_cancel_api.py` が作成されている。ファイル名は `test_*.py` で backend テスト方針と一致する。
- [x] 単体、結合、総合テストの役割が混ざっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体は Fake repository / Fake runner / broker / Port 契約を確認し、結合は FastAPI 経由の SSE/cancel API とアプリ生成時の起動時回復を確認している。総合テスト、Playwright、実 Codex、画面確認は含まれていない。
- [x] テスト方針で求める観点、カバレッジ、証跡、実行環境、完了条件が満たされているか。
  - 検証結果: 指摘あり
  - 確認根拠: Red 報告として `ruff check src/backend/tests` pass、unit `13 failed, 122 passed`、integration `6 failed, 66 passed` があり、失敗理由は F004 未実装起因と整理されている。一方、外部 IF が必須とする SSE `answer` payload の `answer` 本体について、`test_execution_sse_cancel_api.py:90-91` と `tests/support/execution.py:245-253` では検証できないため、SSE IF 契約観点に不足がある。
- [x] テスト方針が実装や設計の現状に追従していない場合は、テスト方針側を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 単体/結合テスト方針は F004 の対象範囲、SSE API、起動時実行回復、docstring、型制約を既に定義しており、方針側の旧化は確認していない。
  - 理由: テスト方針修正が不要なため。

## 単体テスト

- [x] 公開関数、公開メソッド、コンポーネント、純粋ロジックの責務を単位としているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_cancel_and_recovery_use_cases.py` は `CancelChatRunUseCase.execute` と `RecoverUnfinishedRunsUseCase.execute`、`test_sse_event_broker.py` は `RunEventBroker` と `format_sse_event`、`test_chat_port_contracts.py` は公開 Port / DTO 契約を対象にしている。
- [x] 外部副作用を Fake、Stub、Mock、fixture で差し替えているか。
  - 検証結果: 指摘なし
  - 確認根拠: `tests/support/execution.py:97-174` に `FakeExecutionRepository`、`FakeRunEventPublisher`、`FakeCodexRunner`、`FakeBackgroundExecutor` が定義され、単体テストでは DB、SSE 実通信、実 Codex、background 実行を差し替えている。
- [x] 事前条件、事後条件、不変条件、正常系、異常系、境界値、分岐が確認されているか。
  - 検証結果: 指摘なし
  - 確認根拠: キャンセルは accepted、running、completed/error/timed_out/canceled/cancel_requested を確認し、起動時回復は accepted/running/validating/cancel_requested と dispatcher 登録失敗を確認している。SSE broker は state/message/canceled の順序と終端後の追加 publish 抑止を確認している。
- [x] テストが内部実装詳細に密結合しすぎていないか。
  - 検証結果: 指摘なし
  - 確認根拠: テストは application use case、runtime/database Port、SSE broker / formatter など公開境界の import と結果を対象にしている。private 関数や ORM 内部構造への直接依存は確認していない。
- [x] テストが単に例外が出ないことではなく、仕様上意味のある結果、状態変化、副作用、出力を検証しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_cancel_accepted_run_finishes_without_codex_cancel` は戻り値、Codex cancel 未呼出、状態遷移、SSE publish を検証し、`test_recovery_registers_accepted_and_terminalizes_lost_runs` は登録件数、状態終端件数、dispatcher 登録 run、DB 更新依頼を検証している。

## 結合テスト

- [x] 外部インターフェース、処理設計、永続化、ファイル、通信境界、表示または操作連携を設計単位で確認しているか。
  - 検証結果: 指摘あり
  - 確認根拠: `test_execution_sse_cancel_api.py` は IF-SB-06 と IF-SB-07、起動時実行回復の主要境界を確認しているが、外部 IF の `answer` payload 必須項目は `docs/.../画面バックエンドAPI IF.md:868-870` で定義されているのに、`test_execution_sse_cancel_api.py:90-91` では `run_id` と `state` しか確認していない。
- [x] 実外部サービス、実行環境、実行時間や環境差分が大きい対象を不必要に使っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 結合テストは FastAPI、PostgreSQL テスト DB、SSE wire、DB 状態を対象にしており、実 Codex、実ブラウザ、F005 以降の回答検証、成果物配信、F007 の物理削除・回復は起動していない。
- [x] Mock、Fake、Stub が過剰で、実際の契約違反や結合不備を隠していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 生成役報告の integration Red は SSE/cancel API 未登録による 404 と起動時回復未実装による DB 状態未整合を検出している。結合テストでは `ASGITransport` と実 app 生成を通しており、API ルーティング不備を隠していない。
- [x] トランザクション、状態更新、競合、ロールバック、エラー変換、ログ依頼が確認されているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_cancel_api_cancels_accepted_run_and_publishes_terminal_state` と `test_cancel_api_moves_running_run_to_cancel_requested` は DB 上の run 状態変更を確認し、異常系テストは Cookie なし、他ユーザ、終端済み、削除中のエラー変換と既存状態不変を確認している。
- [x] テストデータが独立し、実行順序に依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 各 integration test は `foundation_test_database_url()` と `prepare_foundation_database(database_url)` を使い、必要な user/chat/run をテスト内で seed している。UUID もテスト内で固定しており、別テストの状態共有を前提にしていない。
- [x] 時刻、乱数、実行順序、外部通信、ファイルシステム、DB 状態により不安定になるテストになっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 時刻は `FIXED_CHAT_NOW`、ID は固定 UUID、ファイルは `tmp_path` と `create_foundation_config`、DB はテストごとに準備している。実外部通信や実 Codex 起動はない。
- [x] テストデータが実装ロジックのコピーや都合のよい値だけになっておらず、境界値、異常値、業務上意味のある値を含んでいるか。
  - 検証結果: 指摘なし
  - 確認根拠: テストデータは accepted/running/validating/cancel_requested/completed、未ログイン、他ユーザ、対象なし、削除中、終端済みを含み、F004 の業務境界を代表している。

## 総合テスト

- [x] 利用者が利用者インターフェースまたは実運用に近い経路で業務を完了できることを確認しているか。
  - 検証結果: 対象外
  - 確認根拠: 現フェーズは F004 テストコードレビューであり、機能別総合テストレビューではない。
  - 理由: 総合テスト成果物は今回のレビュー対象外のため。
- [x] 自動確認、手動確認、通信確認、永続化確認、ファイル確認の役割がテスト方針と一致しているか。
  - 検証結果: 対象外
  - 確認根拠: 今回は単体/結合テストコードの先行レビューであり、手動確認や総合テスト分類は作成対象ではない。
  - 理由: 総合テストレビュー対象ではないため。
- [x] 未実施、一部確認、保留、不合格、再テストの記録がテスト仕様・結果に残っているか。
  - 検証結果: 対象外
  - 確認根拠: F004 はまだテストコードレビュー段階であり、機能別総合テスト仕様・結果は後続工程の対象。
  - 理由: 後続フェーズで確認するため。
- [x] 実行証跡とテストケースが追跡できるか。
  - 検証結果: 対象外
  - 確認根拠: 現段階の証跡は生成役報告の Red 結果であり、総合テスト証跡は対象外。
  - 理由: 総合テスト証跡レビューではないため。

## TDD と実装順序

- [x] 実装成果物レビューでは、TDD が要求される範囲で Red、Green、Refactor の証跡または説明があるか。
  - 検証結果: 指摘なし
  - 確認根拠: 生成役報告では、`ruff check src/backend/tests` pass、unit `13 failed, 122 passed`、integration `6 failed, 66 passed` が記録され、失敗理由は `backend.application.execution` 未作成、F004 runtime/database Port 未定義、SSE/cancel API 未登録、起動時回復未実装と説明されている。
- [x] Red を事後的に作れない場合は、レビュー指摘として記録し、今後の修正方針を示す。
  - 検証結果: 対象外
  - 確認根拠: F004 本実装前に Red が成立しているとの生成役報告があり、Red 欠落ではない。
  - 理由: Red 欠落指摘が不要なため。
- [x] テスト追加が不要な場合は、除外理由が方針と整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 はテスト追加フェーズであり、除外は総合テスト、実 Codex、回答検証、成果物配信、F007 物理削除・回復など後続フェーズ/後続機能に限定されている。

## 不要なコメントと作業経緯

- [x] テスト名、docstring、コメント、テスト仕様、証跡に、確認対象の理解や再実行に不要な作業経緯、内部事情、言い訳、暫定理由が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象テスト本文を確認し、docstring は `観点：` と `確認：` で仕様上の確認内容を記載している。`rg` で `TODO`、`FIXME`、`暫定`、`Red`、`未実装`、`とりあえず`、`一旦` 等の作業経緯表現は検出されなかった。
- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 指摘なし
  - 確認根拠: `rg -n "観点：|確認："` で各テストの docstring を確認し、SSE、キャンセル、起動時回復、Port 契約の責務と確認結果を説明している。コードの逐語説明や作業報告は確認していない。
- [x] テスト失敗理由、作成時の都合、環境制約、ツール制約、レビュー指摘への反応など、成果物ではなく作業報告や issue に書くべき内容が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: テスト本文と補助ファイルに Red 失敗理由、環境都合、レビュー反応、作業経緯の記述は確認していない。Red 理由は state/生成役報告側に分離されている。
- [x] `既存実装があるので失敗しない`、`一旦この実装にしている`、`あとで修正する`、`指摘されたため追加`、`カバレッジのため追加`、`環境の都合で確認できない`、`旧仕様ではこうだった`、コードの単なる日本語言い換えなどが残っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象ファイルに対する `rg` 検索で、指定された暫定・作業経緯系の語は検出されなかった。docstring は仕様観点と確認結果に限定されている。
- [x] 業務ルール上の非自明な前提、セキュリティ上の制約、外部仕様に由来する制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行、時刻、ID、ファイル、通信の注意点など、確認や保守に必要な説明は残されているか。
  - 検証結果: 指摘なし
  - 確認根拠: docstring は Cookie なし 401、他ユーザ 404、削除中 409、accepted/running のキャンセル差分、起動時回復の状態別整合、終端イベント後の publish 抑止など、保守に必要な契約を明示している。

## 修正方針の判断

- [x] テスト不足ならテストコード、テスト仕様、証跡のどれを補うかを書く。
  - 検証結果: 指摘あり
  - 確認根拠: SSE `answer` payload の必須 `answer` 本体を検証していないため、`.issue/implement-from-docs/2026-06-22_00-19-32_F004_SSE_answer_payloadを検証していない.md` を作成した。修正対象はテストコードと `tests/support/execution.py` の parser / TypedDict であり、設計書や証跡の修正ではない。
- [x] テストが仕様に従っていて実装が違う場合は、実装側を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 現段階は F004 本実装前のテストコードレビューであり、実装側の仕様不一致は判定対象外。
  - 理由: 実装品質レビューではないため。
- [x] テスト方針が過剰または古い場合は、テスト方針と関連成果物を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: テスト方針の過剰・旧化は確認していない。今回の指摘は既存外部 IF 契約に対するテスト不足である。
  - 理由: テスト方針修正指摘が不要なため。

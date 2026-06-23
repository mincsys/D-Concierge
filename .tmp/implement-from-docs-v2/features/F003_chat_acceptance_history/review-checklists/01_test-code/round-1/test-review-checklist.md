# Test Review Checklist

## テスト方針との整合

- [x] テストコードとテスト仕様が、対応するテスト方針の範囲指定、テスト対象単位、除外範囲に一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `src/backend/tests/unit/application/chat/` は application use case の公開 `execute` 境界、`src/backend/tests/unit/application/ports/test_chat_port_contracts.py` は port/DTO 契約、`src/backend/tests/integration/test_chat_acceptance_history_api.py` は F003 の REST/API と DB 連携を対象にしている。単体テスト方針の配置・Fake 利用、結合テスト方針の REST API 単位に沿う構成であることを確認した。
- [x] テスト関連成果物のディレクトリ構成が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは `src/backend/tests/unit/application/chat/` と `src/backend/tests/unit/application/ports/`、結合テストは `src/backend/tests/integration/`、支援コードは `src/backend/tests/support/chat.py` に配置され、単体テスト方針と結合テスト方針の成果物配置に一致している。
- [x] テスト関連成果物のファイル構成、ファイル名、配置先が、テスト方針、設計書、開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_chat_acceptance_use_cases.py`、`test_chat_history_use_cases.py`、`test_chat_port_contracts.py`、`test_chat_acceptance_history_api.py` はいずれも `test_*.py` 形式で、F003 の新規チャット開始、継続指示、履歴一覧、履歴詳細、port 契約に対応する単位で分割されている。
- [x] 単体、結合、総合テストの役割が混ざっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは Fake repository、Fake dispatcher、固定 ID/時刻で UseCase と port を確認し、結合テストは ASGITransport と PostgreSQL テスト DB を使う API/DB 契約確認に分かれている。Playwright や総合テスト仕様の確認は含まれていない。
- [x] テスト方針で求める観点、カバレッジ、証跡、実行環境、完了条件が満たされているか。
  - 検証結果: 指摘あり
  - 確認根拠: Red 結果は `.tmp/implement-from-docs-v2/features/F003_chat_acceptance_history/state.md` に記録され、docstring 形式も方針の `観点` / `確認` を満たしている。一方で、結合テスト方針が求める認証境界と REST 異常系、処理設計が定義する継続指示の空指示・削除中・dispatcher 登録失敗境界が不足していることを確認した。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_23-00-01_F003保護対象チャットAPIの未ログイン契約が不足.md`
    - `.issue/implement-from-docs/2026-06-21_23-00-02_F003継続指示受付テストが主要異常系を網羅していない.md`
- [x] テスト方針が実装や設計の現状に追従していない場合は、テスト方針側を直す方針を書く。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テスト方針と結合テスト方針は、F003 の application use case、REST API、DB 永続化、認証境界、実 Codex 非使用の確認方針を表現できている。今回見つかった不足はテストコード側の追加で解消でき、テスト方針側の修正は不要である。

## 単体テスト

- [x] 公開関数、公開メソッド、コンポーネント、純粋ロジックの責務を単位としているか。
  - 検証結果: 指摘なし
  - 確認根拠: `StartChatUseCase.execute`、`AppendChatRunUseCase.execute`、`ListChatHistoriesUseCase.execute`、`GetChatDetailUseCase.execute` を command object 経由で呼び出し、port contract は `ChatRepositoryPort` と `RunExecutionDispatcherPort` の公開契約を確認している。
- [x] 外部副作用を Fake、Stub、Mock、fixture で差し替えているか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストでは `FakeChatRepository`、`FakeRunExecutionDispatcher`、`FakeTransactionManager`、`FixedClock`、`FixedUuidGenerator` を使い、DB、時刻、ID、dispatcher 登録の実副作用を差し替えている。
- [x] 事前条件、事後条件、不変条件、正常系、異常系、境界値、分岐が確認されているか。
  - 検証結果: 指摘あり
  - 確認根拠: 新規チャット開始は正常、空指示、dispatcher 登録失敗を確認し、履歴詳細は対象なし/deleting を確認している。一方で `AppendChatRunUseCase` は継続指示本文が空の場合、deleting チャットの場合、dispatcher 登録失敗で保存済み run を `error` へ更新する場合を確認していない。
  - 指摘: `.issue/implement-from-docs/2026-06-21_23-00-02_F003継続指示受付テストが主要異常系を網羅していない.md`
- [x] テストが内部実装詳細に密結合しすぎていないか。
  - 検証結果: 指摘なし
  - 確認根拠: UseCase テストは公開 command/result と repository/dispatcher への依頼結果を確認しており、SQLAlchemy model や private method には依存していない。port contract テストも dataclass フィールドと Protocol 上の公開メソッドの確認に留まっている。
- [x] テストが単に例外が出ないことではなく、仕様上意味のある結果、状態変化、副作用、出力を検証しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 新規チャット開始では title 正規化、run state、SSE URL、transaction commit、dispatcher 登録を確認し、履歴一覧/詳細では owner 分離、deleting 除外、回答ブロック、参照元 URL/locator を確認している。

## 結合テスト

- [x] 外部インターフェース、処理設計、永続化、ファイル、通信境界、表示または操作連携を設計単位で確認しているか。
  - 検証結果: 指摘あり
  - 確認根拠: `GET /api/app-config`、`POST /api/chats/start`、`POST /api/chats/{chat_id}/runs`、`GET /api/chat-histories`、`GET /api/chats/{chat_id}` の正常系と一部異常系は確認されている。一方で、保護対象 API の未ログイン `401` が app-config 以外で未確認であり、継続指示 API の空指示、対象なし、deleting 境界も不足している。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_23-00-01_F003保護対象チャットAPIの未ログイン契約が不足.md`
    - `.issue/implement-from-docs/2026-06-21_23-00-02_F003継続指示受付テストが主要異常系を網羅していない.md`
- [x] 実外部サービス、実行環境、実行時間や環境差分が大きい対象を不必要に使っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは `ASGITransport`、テスト DB、`create_foundation_config` を使い、実 Codex、SSE 接続実体、Playwright、外部サービスは起動しない構成である。F003 受付では SSE URL 文字列だけを契約として確認している。
- [x] Mock、Fake、Stub が過剰で、実際の契約違反や結合不備を隠していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは FastAPI app、presentation、application、DB repository、PostgreSQL test DB を通しており、主要 DB テーブルの保存/参照を `table_count`、`instruction_bodies`、`run_state` で観測している。実 Codex 実行は結合テスト方針の対象外であり、dispatcher 起動本体の代替は妥当である。
- [x] トランザクション、状態更新、競合、ロールバック、エラー変換、ログ依頼が確認されているか。
  - 検証結果: 指摘あり
  - 確認根拠: 新規チャット空指示では DB 未作成、継続指示の未完了 run 競合では新規 run 非作成と既存 state 維持が確認されている。一方で、継続指示の空指示、対象なし、deleting、dispatcher 登録失敗時の保存済み run error 化が不足している。
  - 指摘: `.issue/implement-from-docs/2026-06-21_23-00-02_F003継続指示受付テストが主要異常系を網羅していない.md`
- [x] テストデータが独立し、実行順序に依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 各結合テストは `foundation_test_database_url()` と `prepare_foundation_database(database_url)` で DB を既知状態にし、`seed_chat_user` と固定 UUID をテストごとに用意している。テスト間で共有する可変状態は見つからなかった。
- [x] 時刻、乱数、実行順序、外部通信、ファイルシステム、DB 状態により不安定になるテストになっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 支援コードは `FIXED_CHAT_NOW` と固定 UUID を使い、DB は各テストで初期化される。外部通信や実 Codex は使わず、ファイルパスは `tmp_path` と `create_foundation_config` に閉じている。
- [x] テストデータが実装ロジックのコピーや都合のよい値だけになっておらず、境界値、異常値、業務上意味のある値を含んでいるか。
  - 検証結果: 指摘なし
  - 確認根拠: 空白だけの初回指示、未完了 run 競合、別ユーザ履歴、deleting チャット、完了 run の回答/参照元など、F003 の業務上意味のある境界値と異常値を含んでいる。ただし継続指示の不足分は別項目の指摘として記録した。

## 総合テスト

- [x] 利用者が利用者インターフェースまたは実運用に近い経路で業務を完了できることを確認しているか。
  - 検証結果: 対象外
  - 確認根拠: 今回のレビュー対象は F003 の単体・結合テストコードであり、機能別総合テスト仕様や Playwright/画面操作の結果は含まれていない。
  - 理由: 現在フェーズがテストコードレビュー round-1 のため。
- [x] 自動確認、手動確認、通信確認、永続化確認、ファイル確認の役割がテスト方針と一致しているか。
  - 検証結果: 対象外
  - 確認根拠: F003 の機能別総合テストや正式総合テストの実施記録はまだ作成されておらず、今回の確認対象は自動テストコードのみである。
  - 理由: 総合テスト成果物レビューではないため。
- [x] 未実施、一部確認、保留、不合格、再テストの記録がテスト仕様・結果に残っているか。
  - 検証結果: 対象外
  - 確認根拠: `docs/04_テスト/04_総合テスト/` や `.tmp/.../system-test/` の F003 結果は今回対象に含まれていない。
  - 理由: 総合テスト仕様・結果のレビューではないため。
- [x] 実行証跡とテストケースが追跡できるか。
  - 検証結果: 対象外
  - 確認根拠: 機能別総合テスト証跡は今回のレビュー対象外であり、Red 確認結果は state の記録として確認した。
  - 理由: 総合テスト証跡レビューではないため。

## TDD と実装順序

- [x] 実装成果物レビューでは、TDD が要求される範囲で Red、Green、Refactor の証跡または説明があるか。
  - 検証結果: 指摘なし
  - 確認根拠: `.tmp/implement-from-docs-v2/features/F003_chat_acceptance_history/state.md` に、ruff pass、unit 13 failed/105 passed、integration 7 failed/53 passed、Red 理由が F003 application/API/Port 未実装であることが記録されている。
- [x] Red を事後的に作れない場合は、レビュー指摘として記録し、今後の修正方針を示す。
  - 検証結果: 指摘なし
  - 確認根拠: state に `Red が成立しない理由: なし` と記録され、F003 未実装に起因する失敗として Red が成立しているため、事後 Red 不足の指摘は不要である。
- [x] テスト追加が不要な場合は、除外理由が方針と整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: テスト追加が不要な対象として除外された項目は見つからず、今回の不足は issue としてテスト追加方針に反映した。

## 不要なコメントと作業経緯

- [x] テスト名、docstring、コメント、テスト仕様、証跡に、確認対象の理解や再実行に不要な作業経緯、内部事情、言い訳、暫定理由が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象テストの docstring は `観点` と `確認` で、IF ID、UseCase 責務、DB 契約、field_errors、ユーザ分離など確認内容を説明している。作業経緯やレビュー反応は混入していない。
- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 指摘なし
  - 確認根拠: docstring は「accepted run を保存後に dispatcher 登録」「deleting 除外」「内部情報を返さない」など仕様上の意図と契約を説明しており、コードの単なる言い換えではない。
- [x] テスト失敗理由、作成時の都合、環境制約、ツール制約、レビュー指摘への反応など、成果物ではなく作業報告や issue に書くべき内容が混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: Red の失敗理由は state に記録され、テストコード本文には F003 未実装や環境都合を説明するコメントは含まれていない。
- [x] `既存実装があるので失敗しない`、`一旦この実装にしている`、`あとで修正する`、`指摘されたため追加`、`カバレッジのため追加`、`環境の都合で確認できない`、`旧仕様ではこうだった`、コードの単なる日本語言い換えなどが残っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: `rg` と対象ファイル本文確認により、列挙された暫定文言や旧仕様説明に該当する記述は見つからなかった。
- [x] 業務ルール上の非自明な前提、セキュリティ上の制約、外部仕様に由来する制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行、時刻、ID、ファイル、通信の注意点など、確認や保守に必要な説明は残されているか。
  - 検証結果: 指摘なし
  - 確認根拠: テスト支援コードは固定 ID/時刻、TypedDict payload、Fake repository/dispatcher、DB seed/観測 helper を意味のある型で定義し、テスト本文の docstring は dispatcher 境界、ユーザ分離、deleting 除外、SSE URL 契約を説明している。

## 修正方針の判断

- [x] テスト不足ならテストコード、テスト仕様、証跡のどれを補うかを書く。
  - 検証結果: 指摘あり
  - 確認根拠: 不足は F003 の単体・結合テストコードにあり、docs や方針ではなくテストコードへ未ログイン契約、継続指示の空指示/対象なし/deleting/dispatcher 失敗境界を追加する必要がある。
  - 指摘:
    - `.issue/implement-from-docs/2026-06-21_23-00-01_F003保護対象チャットAPIの未ログイン契約が不足.md`
    - `.issue/implement-from-docs/2026-06-21_23-00-02_F003継続指示受付テストが主要異常系を網羅していない.md`
- [x] テストが仕様に従っていて実装が違う場合は、実装側を直す方針を書く。
  - 検証結果: 指摘なし
  - 確認根拠: 現フェーズは F003 本実装前の Red であり、実装差異ではなくテストコードの網羅不足が問題である。実装側修正を求める段階ではない。
- [x] テスト方針が過剰または古い場合は、テスト方針と関連成果物を直す方針を書く。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テスト方針、結合テスト方針、外部 IF、処理設計は F003 の対象と境界を説明できており、今回の指摘は方針過剰や陳腐化ではなくテストコード不足として扱うのが妥当である。

# Implementation Review Checklist

## 仕様・設計との照合

- [x] 実装が要件、外部設計、内部設計、テスト方針、開発標準と整合しているか。
  - 検証結果: 指摘あり
  - 確認根拠: IF-SB-06/07、SSE購読処理設計、キャンセル処理設計、起動時実行回復処理設計と `src/backend/presentation/rest/chat.py`、`src/backend/application/execution/cancel_chat_run.py`、`src/backend/app/factory.py` を照合し、SSEライブ購読未配線、キャンセル結果未整合、起動時回復対象漏れ、回復ログ不足を issue 化した。
- [x] ディレクトリ構成が設計書や開発標準と一致しているか。
  - 検証結果: 問題なし
  - 確認根拠: F004追加は `src/backend/application/execution/`、`src/backend/presentation/sse/`、既存 `presentation/rest`、`infrastructure/runtime`、`infrastructure/database/repositories` に配置され、開発標準の層構成と一致している。
- [x] ファイル構成、ファイル名、配置先が設計書や開発標準と一致しているか。
  - 検証結果: 問題なし
  - 確認根拠: `cancel_chat_run.py`、`recover_unfinished_runs.py`、`run_event_broker.py`、`payload.py` は処理設計/IF設計の責務単位に対応している。
- [x] 外部インターフェース、永続化、ファイル、設定、ログ、エラー、状態名などが設計された契約と一致しているか。
  - 検証結果: 指摘あり
  - 確認根拠: `subscribe_run_events()` は `text/event-stream` と保存済み payload を返すが RunEventBroker 購読を行わない。`_recover_unfinished_runs()` は回復ログを出さず、`_should_recover_on_startup()` が `cancel_requested` の有無だけで起動時回復を抑止している。
- [x] 設計書にない状態、入出力項目、設定値、永続化項目、操作導線、利用者向け文言が追加されていないか。
  - 検証結果: 問題なし
  - 確認根拠: 状態値は `accepted/running/validating/cancel_requested/canceled/completed/error/timed_out` の既存列挙に収まっており、キャンセル応答も IF-SB-07 の `state` と `user_message` に限定されている。
- [x] 実装が正しく、仕様書側が古い可能性がある場合は、仕様書側の修正方針を書く。
  - 検証結果: 問題なし
  - 確認根拠: 今回の不整合は仕様書側の陳腐化ではなく、実装とテストが現行 docs の `RunEventBroker` 購読、キャンセル結果整合、起動時回復対象、トレースログ契約を満たしていないものとして判断した。
- [x] 対象成果物に存在しない技術要素や実行形態を前提にして指摘していないか。
  - 検証結果: 問題なし
  - 確認根拠: 指摘は現行 docs と実装済み `RunEventBroker`、`CodexRunCancellationLike`、`RecoverUnfinishedRunsUseCase`、`TraceLogWriter` の境界に基づく。F005以降の実Codex実行やF007物理削除そのものは要求していない。

## 責務分割と依存方向

- [x] 層、機能、モジュール、コンポーネントの責務が設計と一致しているか。
  - 検証結果: 指摘あり
  - 確認根拠: SSEの購読/切断検知が `presentation/sse` ではなく REST 関数内の即時 `Response` 組み立てに留まり、SSE購読処理設計の責務分割を満たしていない。
- [x] 副作用を持つ処理が定義済みの境界へ閉じているか。
  - 検証結果: 指摘あり
  - 確認根拠: キャンセル時のイベント発行境界が REST で `_NoopRunEventPublisher` に差し替えられ、RunEventBroker/SSE配信境界へ接続されていない。
- [x] 業務判断やドメイン判断が、表示層、入出力層、インフラ層、設定読込など不適切な場所へ漏れていないか。
  - 検証結果: 指摘あり
  - 確認根拠: `factory.py` の `_should_recover_on_startup()` が起動時回復を `cancel_requested` の有無で抑止しており、状態別回復判断の一部がアプリ組み立て層に漏れている。
- [x] 純粋ロジックが永続化、通信、ファイル、時刻、ID、外部プロセスなどの副作用へ直接依存していないか。
  - 検証結果: 問題なし
  - 確認根拠: `CancelChatRunUseCase` と `RecoverUnfinishedRunsUseCase` は Repository、TransactionManager、Clock、Runner/Executor の Protocol/Port 経由で副作用へ依頼している。
- [x] 上位層が下位層の実装詳細、テスト用実体、内部データ形式へ直接依存していないか。
  - 検証結果: 問題なし
  - 確認根拠: presentation は `SqlAlchemyChatRepository` と `SqlAlchemyTransactionManager` を組み立てる既存パターンを踏襲し、テスト用実体への依存は確認していない。
- [x] 依存方向、公開範囲、再利用単位が設計や開発標準と矛盾していないか。
  - 検証結果: 指摘あり
  - 確認根拠: `RunEventBroker` は application 側にあるが、REST/SSE endpoint と実行側の publish 経路に接続されておらず、設計上の公開再利用単位として機能していない。
- [x] 不要な依存関係、未使用コード、到達不能コード、暫定的な分岐、デバッグ用処理が残っていないか。
  - 検証結果: 指摘あり
  - 確認根拠: `_NoopRunEventPublisher` と `NoopCodexRunCancellation` はF005以降依存を避ける意図はあるが、F004で要求されるSSEイベント配信とキャンセル結果整合まで無効化している。

## 型と構造化データ

- [x] 使用言語、フレームワーク、開発標準に照らして、構造化データが意味のある型、データ構造、スキーマ、列挙値で表現されているか。
  - 検証結果: 問題なし
  - 確認根拠: `CancelChatRunResult`、`RecoverUnfinishedRunsResult`、`CancelRunTarget`、`SseRunSnapshot`、SSE payload TypedDict が定義され、状態は `RunState` を参照している。
- [x] 広すぎる型、未検証の動的データ、説明できない型変換、暗黙のデータ形状に依存していないか。
  - 検証結果: 問題なし
  - 確認根拠: F004本体実装では `Any`、`dict[str, object]`、`cast(...)` への依存は確認していない。SSE payload は TypedDict で表現されている。
- [x] 外部境界、永続化境界、設定境界、表示境界、処理内部のデータ構造が必要に応じて分かれているか。
  - 検証結果: 問題なし
  - 確認根拠: DB DTO、application result、REST response dataclass、SSE TypedDict が分離されている。
- [x] ID、状態、種別、payload、メタデータが文字列や汎用コンテナだけに埋もれず、意味のある表現になっているか。
  - 検証結果: 問題なし
  - 確認根拠: `UUID`、`TraceId`、`RunEventType`、`RunState`、TypedDict payload が使われ、run/chat/trace の区別は維持されている。
- [x] 入力値の検証、正規化、変換が境界で行われ、内部処理が未検証データを前提にしていないか。
  - 検証結果: 問題なし
  - 確認根拠: FastAPIの `UUID` path parameter、`get_authenticated_user`、Repositoryの所有者条件、SSE payload変換関数により境界変換されている。

## エラー・ログ・セキュリティ

- [x] 利用者向けメッセージと内部調査用情報が分離されているか。
  - 検証結果: 問題なし
  - 確認根拠: キャンセル応答は `処理をキャンセルしています。` / `処理をキャンセルしました。` の利用者向け文言に限定され、AppErrorのdiagnosticはHTTP共通エラー変換対象になっている。
- [x] 内部パス、秘密情報、スタックトレース、認証情報、個人情報などが利用者向け出力、外部応答、ログ、証跡へ露出していないか。
  - 検証結果: 問題なし
  - 確認根拠: F004 API応答・SSE payload は run_id/state/text/answer/user_message に限定され、stacktraceやDB URLは外部応答に出していない。
- [x] URL、ポート、ファイルパス、認証情報、環境名、外部サービス名などが不適切にハードコードされていないか。
  - 検証結果: 問題なし
  - 確認根拠: 参照元 URL は既存APIパス `/api/references/{reference_id}` で、ポートや認証情報のハードコードは確認していない。
- [x] エラー分類、追跡情報、状態更新、後続処理の継続または抑止が設計と一致しているか。
  - 検証結果: 指摘あり
  - 確認根拠: `CancelChatRunUseCase` は `CodexRunner.cancel()` の `already_exited` / `not_registered` を状態整合しない。`factory.py` は `SQLAlchemyError` を握りつぶし、回復対象取得失敗の起動時エラー/ログ扱いにしていない。
- [x] ファイルパス、URL、コンテンツ種別、マークアップ、コマンド、外部入力などの検証が境界で行われているか。
  - 検証結果: 問題なし
  - 確認根拠: F004範囲ではファイル配信やコマンド実行本体は追加されていない。SSE endpoint は `media_type="text/event-stream"` を返す。
- [x] 認証、認可、入力制限、出力制御、監査記録が対象システムの設計と整合しているか。
  - 検証結果: 指摘あり
  - 確認根拠: 認証・所有者確認は実装されているが、起動時回復の回復件数・失敗理由のトレースログ記録が未実装で、監査/運用記録の契約を満たさない。

## 実行時制御

- [x] 時刻、乱数、ID、並行処理、リトライ、タイムアウト、リソース解放の扱いが仕様、設計、テストと整合しているか。
  - 検証結果: 指摘あり
  - 確認根拠: `RunEventBroker` に購読解除 API がなく、SSE endpoint も購読登録・接続切断時の解除を行わない。起動時回復も `cancel_requested` がないと未完了runを処理しない。

## コメントと説明

- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 問題なし
  - 確認根拠: 主要クラス/関数のdocstringは責務説明に限定され、レビュー経緯や暫定理由は混入していない。
- [x] 作業都合、環境制約、暫定理由、レビュー対応理由、カバレッジ都合、旧仕様説明、コードの単なる言い換えがコメントや docstring に混入していないか。
  - 検証結果: 問題なし
  - 確認根拠: 実装本文のコメント/docstringに「指摘対応」「暫定」「Red理由」「カバレッジ目的」などの記述は確認していない。
- [x] 業務上の非自明な前提、セキュリティ制約、外部仕様制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行や時刻・ID・通信の注意点など、保守に必要な説明は残されているか。
  - 検証結果: 問題なし
  - 確認根拠: `AcceptedRunBackgroundExecutor` と `NoopCodexRunCancellation` はF004時点の境界意図をdocstringで説明している。ただしこれらが設計契約を満たすかは別項目で指摘済み。

## テストとの対応

- [x] 実装に対応する単体テスト、結合テスト、必要な上位テスト仕様があるか。
  - 検証結果: 指摘あり
  - 確認根拠: F004用単体/結合テストは存在するが、SSE publish後イベント配信、`already_exited` / `not_registered`、`accepted`のみ/`running`のみ/`validating`のみの起動時回復、回復ログ/取得失敗を検出できない。
- [x] 事前条件、事後条件、不変条件、異常系、境界値がテスト対象になっているか。
  - 検証結果: 指摘あり
  - 確認根拠: 認証/所有者/deleting/終端済み/状態更新競合は確認済みだが、上記の主要分岐が不足している。
- [x] 実装変更に対して証跡やテスト方針が古くなっていないか。
  - 検証結果: 指摘あり
  - 確認根拠: 結合 evidence の `design_coverage` は F004 SSE と startup recovery を網羅したように記録しているが、実装とテストは docs の設計単位を満たしていない。
- [x] テストが実装詳細だけを固定せず、仕様上の振る舞いや契約を検証しているか。
  - 検証結果: 指摘あり
  - 確認根拠: `test_app_startup_recovers_unfinished_runs` は `cancel_requested` を同時投入しているため `_should_recover_on_startup()` の実装詳細不備を隠している。SSE結合テストも保存済み応答の組み立てだけで購読契約を検出しない。
- [x] レビュー対象に該当しないテスト種別や証跡形式を必須前提にしていないか。
  - 検証結果: 問題なし
  - 確認根拠: 指摘は単体/結合テストとcoverage evidenceに限定し、総合テストや実Codex起動を前提にしていない。

## 修正方針の判断

- [x] 実装が設計から外れている場合は、実装と関連テストを直す方針を書く。
  - 検証結果: 指摘あり
  - 確認根拠: 4件のissueに、実装修正と不足テスト追加の方針を記録した。
- [x] 設計が実装済みの正しい振る舞いを表せていない場合は、設計とテスト仕様を直す方針を書く。
  - 検証結果: 問題なし
  - 確認根拠: 今回は現行 docs を正として実装側の不足と判断しており、仕様書側修正は不要。
- [x] テストや証跡だけが古い場合は、実装を直す前提にせず、テスト仕様、テストコード、証跡の修正方針を書く。
  - 検証結果: 指摘あり
  - 確認根拠: 実装不備に加えて、検出できていない単体/結合テストと過大な `design_coverage` evidence の更新が必要。
- [x] 判断にユーザ合意が必要な場合は、どの成果物を確定根拠にするかを修正方針に書く。
  - 検証結果: 問題なし
  - 確認根拠: 判断は現行 docs と実装本文の照合で可能で、TBC候補やユーザ合意待ちはない。
- [x] 特定のアプリ、言語、通信方式、画面構成、保存方式に依存した判断ではなく、レビュー対象の仕様と設計に基づいて指摘する。
  - 検証結果: 問題なし
  - 確認根拠: 指摘はD-ConciergeのF004設計文書、テスト方針、開発標準に基づく。

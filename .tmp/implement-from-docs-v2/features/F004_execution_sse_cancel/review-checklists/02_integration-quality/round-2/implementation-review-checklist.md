# Implementation Review Checklist

## 仕様・設計との照合

- [x] 実装が要件、外部設計、内部設計、テスト方針、開発標準と整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `src/backend/presentation/rest/chat.py` の SSE/キャンセル API、`src/backend/application/execution/` の cancellation/recovery/broker 実装、`src/backend/app/factory.py` の起動時回復配線を、SSE購読処理設計、キャンセル処理設計、起動時実行回復処理設計、内部IF設計、テスト方針と照合した。
- [x] ディレクトリ構成が設計書や開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 の application 実装は `application/execution/`、SSE payload は `presentation/sse/`、REST 配線は `presentation/rest/chat.py`、runtime 実装は `infrastructure/runtime/`、DB 拡張は `infrastructure/database/repositories/chat.py` に収まっている。
- [x] ファイル構成、ファイル名、配置先が設計書や開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `cancel_chat_run.py`、`recover_unfinished_runs.py`、`run_event_broker.py`、`interfaces.py`、`dto.py` は F004 の処理・IF 単位と対応しており、チャット受付や履歴再表示の既存ファイルへ不自然に混在していない。
- [x] 外部インターフェース、永続化、ファイル、設定、ログ、エラー、状態名などが設計された契約と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `GET /api/chats/{chat_id}/runs/{run_id}/sse` は `StreamingResponse`、`POST /api/chats/{chat_id}/runs/{run_id}/cancel` はキャンセル受付契約、run 状態は `accepted/running/validating/cancel_requested/canceled/error/completed` 系の設計状態を使用し、起動時回復ログは `startup_recovery_completed` / `startup_recovery_failed` として trace log に記録される。
- [x] 設計書にない状態、入出力項目、設定値、永続化項目、操作導線、利用者向け文言が追加されていないか。
  - 検証結果: 指摘なし
  - 確認根拠: F005 以降の Codex 実行本体、回答検証、成果物配信、F007 の物理削除・回復は実装されておらず、F004 に必要な run 状態制御、SSE、キャンセル、起動時回復の境界に留まっている。
- [x] 実装が正しく、仕様書側が古い可能性がある場合は、仕様書側の修正方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 今回確認した範囲では仕様書側が古いと判断する差分はなく、docs 正本の修正方針を起票する対象はない。
- [x] 対象成果物に存在しない技術要素や実行形態を前提にして指摘していないか。
  - 検証結果: 指摘なし
  - 確認根拠: レビューは FastAPI REST/SSE、PostgreSQL repository、application use case、runtime dispatcher、trace log の既存構成に限定し、画面操作や F005 以降の実行本体を前提にしていない。

## 責務分割と依存方向

- [x] 層、機能、モジュール、コンポーネントの責務が設計と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: cancellation/recovery/broker は application 層、DB 更新は repository、SSE wire 変換は presentation、起動時配線は app factory に分かれている。
- [x] 副作用を持つ処理が定義済みの境界へ閉じているか。
  - 検証結果: 指摘なし
  - 確認根拠: DB 更新は `ChatRepositoryPort` 経由、Codex キャンセルは `CodexRunCancellationLike` 経由、イベント配信は `RunEventPublisherLike`/`RunEventBroker` 経由、trace log は factory の起動時回復ログ境界で扱われている。
- [x] 業務判断やドメイン判断が、表示層、入出力層、インフラ層、設定読込など不適切な場所へ漏れていないか。
  - 検証結果: 指摘なし
  - 確認根拠: キャンセル状態遷移は `CancelChatRunUseCase`、起動時回復判断は `RecoverUnfinishedRunsUseCase` と factory の起動時制御に閉じ、REST 層は認証・リクエスト変換・応答変換に留まっている。
- [x] 純粋ロジックが永続化、通信、ファイル、時刻、ID、外部プロセスなどの副作用へ直接依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: UseCase は port/interface を受け取り、DB session、Codex cancel 実装、broker 実体へ直接依存していない。
- [x] 上位層が下位層の実装詳細、テスト用実体、内部データ形式へ直接依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: `presentation/rest/chat.py` は app state の broker と application port を通じて処理し、テスト用 fake や repository 実装詳細への依存はない。
- [x] 依存方向、公開範囲、再利用単位が設計や開発標準と矛盾していないか。
  - 検証結果: 指摘なし
  - 確認根拠: application から presentation/infrastructure への逆依存は確認されず、`interfaces.py` と `dto.py` で公開契約が分離されている。
- [x] 不要な依存関係、未使用コード、到達不能コード、暫定的な分岐、デバッグ用処理が残っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 生成役報告の `ruff check` / `mypy` pass と、本文確認でデバッグ出力・暫定コメント・到達不能なレビュー対応分岐は見当たらない。

## 型と構造化データ

- [x] 使用言語、フレームワーク、開発標準に照らして、構造化データが意味のある型、データ構造、スキーマ、列挙値で表現されているか。
  - 検証結果: 指摘なし
  - 確認根拠: `CodexCancelStatus` / `CodexCancelResult`、run event DTO、SSE payload、repository DTO が定義され、キャンセル結果や SSE payload が裸の辞書に埋もれていない。
- [x] 広すぎる型、未検証の動的データ、説明できない型変換、暗黙のデータ形状に依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 対象実装・テスト補助で安易な `Any`、`object`、`dict[str, object]`、`cast(...)` への逃避は確認されず、SSE JSON parser は `JsonValue` と `TypedDict` で境界を表現している。
- [x] 外部境界、永続化境界、設定境界、表示境界、処理内部のデータ構造が必要に応じて分かれているか。
  - 検証結果: 指摘なし
  - 確認根拠: REST schema、SSE payload、application DTO、database DTO が分離され、SSE wire 形式は `presentation/sse/payload.py` で整形されている。
- [x] ID、状態、種別、payload、メタデータが文字列や汎用コンテナだけに埋もれず、意味のある表現になっているか。
  - 検証結果: 指摘なし
  - 確認根拠: cancel result status は Literal、run event は DTO/constructor、起動時回復 summary は明示的な集計値で扱われている。
- [x] 入力値の検証、正規化、変換が境界で行われ、内部処理が未検証データを前提にしていないか。
  - 検証結果: 指摘なし
  - 確認根拠: REST 層で認証・所有者・削除中状態・not found 境界を処理し、UseCase は repository から得た対象 run/chat の状態に基づいて遷移する。

## エラー・ログ・セキュリティ

- [x] 利用者向けメッセージと内部調査用情報が分離されているか。
  - 検証結果: 指摘なし
  - 確認根拠: REST エラーは共通エラー形式で返し、起動時回復の取得失敗詳細は trace log に記録され、利用者向け応答へ露出しない。
- [x] 内部パス、秘密情報、スタックトレース、認証情報、個人情報などが利用者向け出力、外部応答、ログ、証跡へ露出していないか。
  - 検証結果: 指摘なし
  - 確認根拠: SSE/REST 応答に内部 path や stacktrace を返す処理はなく、trace log は管理者調査用境界として扱われている。
- [x] URL、ポート、ファイルパス、認証情報、環境名、外部サービス名などが不適切にハードコードされていないか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 実装に環境依存 URL/ポート/認証情報の追加は確認されず、テストデータの URL は参照元 payload の検証値に留まる。
- [x] エラー分類、追跡情報、状態更新、後続処理の継続または抑止が設計と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `already_exited` / `not_registered` は回答未採用 run を `canceled` へ整合し、起動時回復対象取得失敗は `startup_recovery_failed` としてログ化して起動継続する。
- [x] ファイルパス、URL、コンテンツ種別、マークアップ、コマンド、外部入力などの検証が境界で行われているか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 で新たにファイルパスや任意コマンド入力を受け付ける実装はなく、REST/SSE の入力は path parameter と認証済み user context に限定される。
- [x] 認証、認可、入力制限、出力制御、監査記録が対象システムの設計と整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: SSE/cancel API は認証必須、他ユーザ・削除中・not found 境界を確認する結合テストがあり、起動時回復ログも trace log として記録される。

## 実行時制御

- [x] 時刻、乱数、ID、並行処理、リトライ、タイムアウト、リソース解放の扱いが仕様、設計、テストと整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: SSE は terminal/disconnect で `RunEventBroker.unsubscribe()` を呼び、起動時回復は未完了 run が存在する場合に実行し、dispatcher 多重登録や terminal event 後 publish の境界は broker/use case テストで確認されている。

## コメントと説明

- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 指摘なし
  - 確認根拠: F004 実装本文にレビュー対応理由や作業経緯を説明するコメントは確認されず、コメントは非自明な契約や境界の補足に留まる。
- [x] 作業都合、環境制約、暫定理由、レビュー対応理由、カバレッジ都合、旧仕様説明、コードの単なる言い換えがコメントや docstring に混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: `src/backend/application/execution/`、`src/backend/presentation/rest/chat.py`、`src/backend/app/factory.py` の確認で、Red/Green 経緯や issue 対応の説明は成果物に混入していない。
- [x] 業務上の非自明な前提、セキュリティ制約、外部仕様制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行や時刻・ID・通信の注意点など、保守に必要な説明は残されているか。
  - 検証結果: 指摘なし
  - 確認根拠: SSE 購読解除、terminal event、起動時回復失敗ログ、キャンセル結果整合はテスト名と構造から意図を追跡でき、保守上必要な境界は欠落していない。

## テストとの対応

- [x] 実装に対応する単体テスト、結合テスト、必要な上位テスト仕様があるか。
  - 検証結果: 指摘なし
  - 確認根拠: `test_cancel_and_recovery_use_cases.py`、`test_sse_event_broker.py`、`test_execution_sse_cancel_api.py` がキャンセル、SSE、起動時回復、ログ境界を検証している。
- [x] 事前条件、事後条件、不変条件、異常系、境界値がテスト対象になっているか。
  - 検証結果: 指摘なし
  - 確認根拠: 未ログイン、他ユーザ、deleting/not found、terminal 状態、runner 完了済み、起動時回復対象取得失敗、broker unsubscribe identity が確認対象になっている。
- [x] 実装変更に対して証跡やテスト方針が古くなっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: evidence は round-2 修正後の `2026-06-22T06:17:31+09:00`、単体 144 passed、結合 83 passed、coverage unit 95.88%、integration 80.92% に更新されている。
- [x] テストが実装詳細だけを固定せず、仕様上の振る舞いや契約を検証しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 結合テストは HTTP/SSE payload、DB 状態、trace log、認証境界を検証し、単体テストは UseCase と broker の公開契約に沿っている。
- [x] レビュー対象に該当しないテスト種別や証跡形式を必須前提にしていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 今回は結合・品質レビューであり、機能別総合テストや Playwright 証跡を合否前提にしていない。

## 修正方針の判断

- [x] 実装が設計から外れている場合は、実装と関連テストを直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 設計から外れた実装は確認されず、新規 issue と修正方針は不要。
- [x] 設計が実装済みの正しい振る舞いを表せていない場合は、設計とテスト仕様を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 設計書側の不足または古さとして扱うべき差分は確認していない。
- [x] テストや証跡だけが古い場合は、実装を直す前提にせず、テスト仕様、テストコード、証跡の修正方針を書く。
  - 検証結果: 対象外
  - 確認根拠: テスト・証跡は round-2 修正後の状態へ更新済みで、古い証跡を起点にした指摘はない。
- [x] 判断にユーザ合意が必要な場合は、どの成果物を確定根拠にするかを修正方針に書く。
  - 検証結果: 対象外
  - 確認根拠: TBC やユーザ合意が必要な仕様判断は発生していない。
- [x] 特定のアプリ、言語、通信方式、画面構成、保存方式に依存した判断ではなく、レビュー対象の仕様と設計に基づいて指摘する。
  - 検証結果: 指摘なし
  - 確認根拠: 指摘判断は F004 関連 docs、内部IF、テスト方針、開発標準と実装本文の照合に基づく。

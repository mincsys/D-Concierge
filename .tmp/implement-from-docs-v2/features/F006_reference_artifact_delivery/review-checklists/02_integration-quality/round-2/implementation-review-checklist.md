# Implementation Review Checklist

## 仕様・設計との照合

- [x] 実装が要件、外部設計、内部設計、テスト方針、開発標準と整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `GetReferenceDataUseCase`、`GetArtifactUseCase`、`FileReferenceStore`、`FileArtifactStore`、`delivery.py` は、IF-SB-08/09、参照元PDF取得処理設計、Codex成果物配信処理設計の所有者確認、削除中拒否、許可範囲内ファイル配信、保存済みMIME配信、欠損404、許可外403と整合している。round-1 指摘のMIME/拡張子不一致は `ARTIFACT_MIME_TYPES_BY_SUFFIX` と `_mime_type_for_storage_path()` で配信前に拒否され、保存済み成果物欠損は `trace=True` で記録対象になっている。
- [x] ディレクトリ構成が設計書や開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: UseCaseは `src/backend/application/references/` と `src/backend/application/artifacts/`、Port/DTOは `src/backend/application/ports/`、Storeは `src/backend/infrastructure/filesystem/`、DB Repositoryは `src/backend/infrastructure/database/repositories/`、REST境界は `src/backend/presentation/rest/` に配置されている。
- [x] ファイル構成、ファイル名、配置先が設計書や開発標準と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: `get_reference_data.py`、`get_artifact.py`、`reference_store.py`、`artifact_store.py`、`delivery.py`、`registration.py` は対象責務に対応し、router登録も既存 `register_routes()` に閉じている。
- [x] 外部インターフェース、永続化、ファイル、設定、ログ、エラー、状態名などが設計された契約と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: REST URLは `/api/references/{reference_id}` と `/api/artifacts/{artifact_id}`、DB読取は `SqlAlchemyChatRepository`、ファイル境界は `FileReferenceStore` / `FileArtifactStore`、エラー分類は `AppError` / `ErrorType`、ログ記録要否は `trace` で制御されている。成果物のMIME/拡張子不一致は403、保存済み成果物欠損は404かつtrace対象である。
- [x] 設計書にない状態、入出力項目、設定値、永続化項目、操作導線、利用者向け文言が追加されていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 新規状態、DB項目、設定項目、画面導線は追加されていない。既存の `data_source.dir`、`generator.saved_artifacts_dir`、共通エラー応答、FileResponseを利用している。
- [x] 実装が正しく、仕様書側が古い可能性がある場合は、仕様書側の修正方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 今回のround-2差分は仕様書側修正ではなく、実装が既存設計へ追従した修正である。
  - 理由: 仕様書側修正対象ではないため。
- [x] 対象成果物に存在しない技術要素や実行形態を前提にして指摘していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 確認はFastAPI REST、SQLAlchemy Repository、ファイルStore、AppError/TraceLog、pytest evidenceという実在成果物だけに基づく。

## 責務分割と依存方向

- [x] 層、機能、モジュール、コンポーネントの責務が設計と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: presentationは認証・設定取得・UseCase呼出・FileResponse化、applicationはRepository/Store調停と業務分類、infrastructureはDB/ファイル実体を扱っている。
- [x] 副作用を持つ処理が定義済みの境界へ閉じているか。
  - 検証結果: 指摘なし
  - 確認根拠: DB読込は `SqlAlchemyChatRepository`、ファイル解決と読込確認は `FileReferenceStore` / `FileArtifactStore`、HTTP応答は `delivery.py` に閉じている。
- [x] 業務判断やドメイン判断が、表示層、入出力層、インフラ層、設定読込など不適切な場所へ漏れていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 所有者・削除中判定はRepository、PDF種別と成果物MIME/拡張子対応はUseCase、パス許可範囲はStore/PathSecurityServiceで扱う。
- [x] 純粋ロジックが永続化、通信、ファイル、時刻、ID、外部プロセスなどの副作用へ直接依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: UseCaseはPort抽象とDTOへ依存し、SQLAlchemyやファイルI/Oを直接扱っていない。
- [x] 上位層が下位層の実装詳細、テスト用実体、内部データ形式へ直接依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: UseCaseはProtocol/DTOに依存し、SQLAlchemy modelやテストFakeへ依存しない。presentationは既存の具象組立パターンでRepository/Storeを生成するだけである。
- [x] 依存方向、公開範囲、再利用単位が設計や開発標準と矛盾していないか。
  - 検証結果: 指摘なし
  - 確認根拠: applicationからinfrastructureへの直接依存はなく、infrastructureがapplicationのPort DTOを実装している。router登録は `register_routes()` に集約されている。
- [x] 不要な依存関係、未使用コード、到達不能コード、暫定的な分岐、デバッグ用処理が残っていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象実装にデバッグ出力、暫定コメント、到達不能に見える分岐は確認されず、生成役報告ではruff check passが示されている。

## 型と構造化データ

- [x] 使用言語、フレームワーク、開発標準に照らして、構造化データが意味のある型、データ構造、スキーマ、列挙値で表現されているか。
  - 検証結果: 指摘なし
  - 確認根拠: Command/Result/Opened DTO は dataclass、PortはProtocol、DB戻り値は `DisplayReferenceData` / `ArtifactData`、エラー分類は `ErrorType` で表現されている。
- [x] 広すぎる型、未検証の動的データ、説明できない型変換、暗黙のデータ形状に依存していないか。
  - 検証結果: 指摘なし
  - 確認根拠: `ReferenceModel.locator` は `_reference_data()` で型検証後にDTO化している。対象実装に広すぎる `Any`、説明不能な `cast(...)`、戻り値を隠す `object` は確認されない。
- [x] 外部境界、永続化境界、設定境界、表示境界、処理内部のデータ構造が必要に応じて分かれているか。
  - 検証結果: 指摘なし
  - 確認根拠: DB model、application DTO、filesystem DTO、HTTP FileResponseが分離されており、DB modelを直接HTTP応答へ返していない。
- [x] ID、状態、種別、payload、メタデータが文字列や汎用コンテナだけに埋もれず、意味のある表現になっているか。
  - 検証結果: 指摘なし
  - 確認根拠: `reference_id` / `artifact_id` はUUID、チャット状態は `ChatState`、run状態は `RunState`、参照元/成果物メタは専用DTOで表現されている。
- [x] 入力値の検証、正規化、変換が境界で行われ、内部処理が未検証データを前提にしていないか。
  - 検証結果: 指摘なし
  - 確認根拠: UUID path parameter、locator型、PDF拡張子、保存済み成果物の許可MIME、保存済み成果物の拡張子とMIMEタイプの対応、保存領域内パスが境界で検証されている。

## エラー・ログ・セキュリティ

- [x] 利用者向けメッセージと内部調査用情報が分離されているか。
  - 検証結果: 指摘なし
  - 確認根拠: 実装は `AppError` と共通RESTエラー変換を使い、利用者向け応答は共通メッセージ、内部診断は `diagnostic_message` と `trace` に分離している。
- [x] 内部パス、秘密情報、スタックトレース、認証情報、個人情報などが利用者向け出力、外部応答、ログ、証跡へ露出していないか。
  - 検証結果: 指摘なし
  - 確認根拠: REST応答はFileResponseまたは共通エラーpayloadであり、結合テストは内部パスやstorage_pathを本文へ含めないことを確認している。coverage evidenceにも秘密情報や絶対パスはない。
- [x] URL、ポート、ファイルパス、認証情報、環境名、外部サービス名などが不適切にハードコードされていないか。
  - 検証結果: 指摘なし
  - 確認根拠: API URLは外部IF定義の `/api/references/{reference_id}` と `/api/artifacts/{artifact_id}`、ファイルルートは設定値から取得され、認証情報のハードコードはない。
- [x] エラー分類、追跡情報、状態更新、後続処理の継続または抑止が設計と一致しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象なし404、削除中409、許可外MIME/拡張子不一致403、参照元欠損404、成果物欠損404かつtrace対象、読込失敗500が設計と一致している。
- [x] ファイルパス、URL、コンテンツ種別、マークアップ、コマンド、外部入力などの検証が境界で行われているか。
  - 検証結果: 指摘なし
  - 確認根拠: `PathSecurityService` による範囲検証、UseCaseによる成果物MIME許可と拡張子対応検証、`FileResponse` の `media_type` 指定、`nosniff` ヘッダーが確認できる。
- [x] 認証、認可、入力制限、出力制御、監査記録が対象システムの設計と整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: 認証Cookie、所有者絞り込み、削除中拒否、本文非露出、成果物欠損時のtraceログ確認がテストで扱われている。

## 実行時制御

- [x] 時刻、乱数、ID、並行処理、リトライ、タイムアウト、リソース解放の扱いが仕様、設計、テストと整合しているか。
  - 検証結果: 指摘なし
  - 確認根拠: F006配信は読み取り処理であり、追加の並行制御やリトライを導入していない。DB sessionはcontext manager、ファイル読込確認はwith文、配信はFileResponseで扱われる。

## コメントと説明

- [x] コメントや docstring は、仕様上の意図、契約、前提条件、非自明な制約の説明に限定されているか。
  - 検証結果: 指摘なし
  - 確認根拠: 実装docstringは参照元PDF取得、成果物取得、保存済み成果物配信境界など役割説明に限定されている。
- [x] 作業都合、環境制約、暫定理由、レビュー対応理由、カバレッジ都合、旧仕様説明、コードの単なる言い換えがコメントや docstring に混入していないか。
  - 検証結果: 指摘なし
  - 確認根拠: 対象実装に「暫定」「レビュー対応」「カバレッジのため」などの作業経緯コメントは確認されなかった。
- [x] 業務上の非自明な前提、セキュリティ制約、外部仕様制約、特定テストデータが必要な理由、mock/fake/stub の境界理由、並行実行や時刻・ID・通信の注意点など、保守に必要な説明は残されているか。
  - 検証結果: 指摘なし
  - 確認根拠: セキュリティ制約は `PathSecurityService`、UseCase名、Store名、テストdocstringから追跡できる。追加で必要な説明不足は確認されなかった。

## テストとの対応

- [x] 実装に対応する単体テスト、結合テスト、必要な上位テスト仕様があるか。
  - 検証結果: 指摘なし
  - 確認根拠: 単体テストは参照元/成果物UseCaseとPort契約を確認し、結合テストはIF-SB-08/09のREST、認証、DB、一時ファイル、エラー変換、trace記録を確認している。
- [x] 事前条件、事後条件、不変条件、異常系、境界値がテスト対象になっているか。
  - 検証結果: 指摘なし
  - 確認根拠: 所有者、別ユーザ、削除中、未ログイン、欠損、読込失敗、traversal、許可外MIME、MIME/拡張子不一致、HTML/CSV正常配信、成果物欠損traceがテスト対象になっている。
- [x] 実装変更に対して証跡やテスト方針が古くなっていないか。
  - 検証結果: 指摘なし
  - 確認根拠: coverage evidenceはF006修正後の単体241 passed、結合137 passed、branch coverage passを記録している。テスト方針側が古いとは判断しない。
- [x] テストが実装詳細だけを固定せず、仕様上の振る舞いや契約を検証しているか。
  - 検証結果: 指摘なし
  - 確認根拠: テストはREST status、Content-Type、本文、内部パス非露出、エラーpayload、traceログ、Store呼出有無を確認しており、private実装の処理順に依存していない。
- [x] レビュー対象に該当しないテスト種別や証跡形式を必須前提にしていないか。
  - 検証結果: 指摘なし
  - 確認根拠: 今回は結合テスト完了検証と実装品質レビューであり、総合テストやPlaywright証跡は必須条件として扱っていない。

## 修正方針の判断

- [x] 実装が設計から外れている場合は、実装と関連テストを直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: round-2確認時点で設計から外れる未解決の実装差分は確認されなかった。
  - 理由: 新規修正方針を要する指摘がないため。
- [x] 設計が実装済みの正しい振る舞いを表せていない場合は、設計とテスト仕様を直す方針を書く。
  - 検証結果: 対象外
  - 確認根拠: 設計側の古さや過剰指定は確認されなかった。
  - 理由: 設計修正対象ではないため。
- [x] テストや証跡だけが古い場合は、実装を直す前提にせず、テスト仕様、テストコード、証跡の修正方針を書く。
  - 検証結果: 対象外
  - 確認根拠: テスト・証跡だけが古い状態は確認されなかった。
  - 理由: テスト・証跡のみの修正対象ではないため。
- [x] 判断にユーザ合意が必要な場合は、どの成果物を確定根拠にするかを修正方針に書く。
  - 検証結果: 対象外
  - 確認根拠: 対象docsと実装・テストから判定でき、追加合意は不要と判断した。
  - 理由: 判断不能ではないため。
- [x] 特定のアプリ、言語、通信方式、画面構成、保存方式に依存した判断ではなく、レビュー対象の仕様と設計に基づいて指摘する。
  - 検証結果: 指摘なし
  - 確認根拠: 判断はF006の内部設計、外部IF、ファイルIF、処理設計、テスト方針に基づいている。

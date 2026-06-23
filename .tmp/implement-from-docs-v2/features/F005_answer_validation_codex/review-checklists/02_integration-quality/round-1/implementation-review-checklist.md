# 実装レビュー checklist

対象: F005 Codex実行・回答検証・採用保存 結合テスト完了検証・実装コード品質レビュー round-1

## 1. 仕様・設計整合

- [x] 実装が対象仕様・設計書の機能要件を満たしている
  - 検証結果: 指摘あり
  - 確認根拠: API受付は `NullRunExecutionDispatcher` のままで F005 実行本体へ配線されていないため、`.issue/implement-from-docs/2026-06-22_08-30-01_F005チャット受付APIからCodex実行が起動されない.md` を作成した。
- [x] 入出力契約、DTO、永続化項目が設計と一致している
  - 検証結果: 指摘あり
  - 確認根拠: `ValidateAnswerUseCase` が `ValidatorCodexRequest.user_id` に空文字を渡しており、Codex実行IFの `<user-id>/<session-id>` 作業領域契約と不一致。issue `2026-06-22_08-30-03` を作成した。
- [x] 正常系の処理シーケンスが設計どおりである
  - 検証結果: 指摘あり
  - 確認根拠: `ExecuteChatRunUseCase` の生成、検証、採用保存の基本順序はあるが、再生成時に `running` へ戻らない。issue `2026-06-22_08-30-02` を作成した。
- [x] 異常系・境界値の処理が設計どおりである
  - 検証結果: 指摘あり
  - 確認根拠: 空回答本文、成果物リンク形式・拡張子の固定検証が設計と不一致。issue `2026-06-22_08-30-04`、`2026-06-22_08-30-05` を作成した。
- [x] トランザクション境界とロールバック方針が設計と一致している
  - 検証結果: 概ね適合
  - 確認根拠: `ExecuteChatRunUseCase` は状態更新、メッセージ保存、回答保存ごとに `transaction_manager` を使い、Codex実行とSSEをDBトランザクション外に置いている。
- [x] 設定値・環境値・タイムアウトの扱いが設計と一致している
  - 検証結果: 指摘あり
  - 確認根拠: 残り秒数を `execution_deadline_at` から算出する実装はあるが、実運用配線がないため設定済みCodex実行設定がAPI経路で使われない。issue `2026-06-22_08-30-01` に含めた。
- [x] 既存機能の契約を破壊していない
  - 検証結果: 報告上は適合
  - 確認根拠: 生成役報告では F001-F004 を含む単体217件、結合99件がpass。レビュー上も既存REST応答やSSE payloadの型崩れは確認していない。

## 2. アーキテクチャ・責務分割

- [x] レイヤ境界と依存方向が守られている
  - 検証結果: 指摘あり
  - 確認根拠: application層からinfrastructure層への直接依存は見当たらないが、presentation層からF005実行境界への配線が欠落している。issue `2026-06-22_08-30-01`。
- [x] domain/application/infrastructure/presentationの責務が混在していない
  - 検証結果: 概ね適合
  - 確認根拠: Codex実行は `infrastructure/codex`、検証・実行調停は `application`、REST/SSE整形は `presentation` に分かれている。
- [x] Port/Adapter境界が設計どおりである
  - 検証結果: 指摘あり
  - 確認根拠: Codex/Filesystem Port自体は定義されているが、API受付dispatcherが実行Adapterへ接続されていない。issue `2026-06-22_08-30-01`。
- [x] shared/commonへの依存が過剰でない
  - 検証結果: 適合
  - 確認根拠: `AppError`、`ErrorType`、`RunState`、trace idなど既存共通要素への依存に留まる。
- [x] F005の責務を超えたF006/F007実装を含んでいない
  - 検証結果: 適合
  - 確認根拠: 参照元/成果物表示UI、チャット物理削除、アカウント物理削除回復などは実装対象にしていない。
- [x] 既存のディレクトリ構成・命名規約に従っている
  - 検証結果: 適合
  - 確認根拠: `application/execution`、`application/validation`、`application/artifacts`、`infrastructure/codex`、`infrastructure/filesystem` の配置は既存構成に沿っている。
- [x] 不要な抽象化や過剰な汎用化がない
  - 検証結果: 概ね適合
  - 確認根拠: Protocol/DTOは境界ごとに限定されている。過剰な汎用型の使用は対象検索で見当たらない。

## 3. 型・データ構造

- [x] `Any`、広すぎる `object`、`dict[str, object]`、安易な `cast(...)` を使っていない
  - 検証結果: 適合
  - 確認根拠: 対象 implementation/test/support に対する検索で該当なし。JSON境界は `JsonValue` や `TypedDict` を使用している。
- [x] 構造化payloadはTypedDict/dataclass等で表現されている
  - 検証結果: 適合
  - 確認根拠: Codex request/result、validation result、artifact result、SSE/REST payload は dataclass、Protocol、TypedDict で表現されている。
- [x] None許容と必須項目の扱いが明確である
  - 検証結果: 指摘あり
  - 確認根拠: `ValidatorCodexRequest.user_id` は必須文字列だが空文字固定で、必須値として扱えていない。issue `2026-06-22_08-30-03`。
- [x] Enum/リテラル値が設計と一致している
  - 検証結果: 適合
  - 確認根拠: `ValidationStatus`、`RunState`、Codex JSONL event type は設計の状態名に対応している。
- [x] DB保存用データとAPI/SSE表示用データが混線していない
  - 検証結果: 概ね適合
  - 確認根拠: `AnswerData` と presentation payload は分離されている。ただし成果物リンクの抽出・置換仕様には issue `2026-06-22_08-30-04` がある。

## 4. エラー処理・ログ・セキュリティ

- [x] AppErrorのerror_type/trace/diagnostic_messageが妥当である
  - 検証結果: 概ね適合
  - 確認根拠: PDF読込不能、Codex失敗、成果物保存失敗は trace 対象のSYSTEMとして扱っている。
- [x] 利用者向けメッセージに内部情報を漏らしていない
  - 検証結果: 適合
  - 確認根拠: Codex失敗や採用失敗時は汎用メッセージ、PDF読込失敗は固定メッセージへ変換している。
- [x] traceログに調査に必要な情報を残している
  - 検証結果: 注意あり
  - 確認根拠: stage/diagnosticは残るが trace_id/run_id を直接含める設計より簡略。今回の主要不合格は別issueに切り出し、ログ詳細は修正時に再確認が必要。
- [x] ファイルパス・成果物パスの安全性を検証している
  - 検証結果: 指摘あり
  - 確認根拠: パストラバーサルや絶対パス検査はあるが、許可拡張子とHTMLリンク対象が設計不一致。issue `2026-06-22_08-30-04`。
- [x] Docker/Codex起動のタイムアウト・失敗時処理がある
  - 検証結果: 部分適合
  - 確認根拠: `CodexRunner._run_codex` は timeout/non-zero/error を `AppError` 化する。一方、API受付から実行されないため実運用経路は未成立。issue `2026-06-22_08-30-01`。
- [x] 機密情報・絶対パス・標準出力を利用者向けに漏らしていない
  - 検証結果: 適合
  - 確認根拠: progressは `payload.kind="progress"` のtextのみ、final JSONやstderrは利用者向け回答に出していない。

## 5. 実行制御・副作用境界

- [x] Codex実行、検証、成果物保存、DB保存、SSE配信の副作用境界が分離されている
  - 検証結果: 指摘あり
  - 確認根拠: ユースケース内の副作用境界は分離されているが、API受付から実行副作用へ接続されていない。issue `2026-06-22_08-30-01`。

## 6. コメント・docstring・命名

- [x] docstringは責務説明に留まり、作業経緯やRed理由を含まない
  - 検証結果: 適合
  - 確認根拠: 対象コード検索でRed理由、暫定、作業経緯の混入は見当たらない。
- [x] コメントは必要最小限で実装意図を補足している
  - 検証結果: 適合
  - 確認根拠: 過剰なコメントや古い仕様の説明は確認していない。
- [x] 命名が設計用語と一致している
  - 検証結果: 概ね適合
  - 確認根拠: Execute/Validate/SaveAdoptedArtifacts/CodexRunner等は設計用語と対応している。

## 7. テストとの整合

- [x] 実装がテストの期待だけに寄ったものになっていない
  - 検証結果: 指摘あり
  - 確認根拠: 結合テストは `ExecuteChatRunUseCase` を手動起動しており、API受付からの実行配線欠落を検出していない。issue `2026-06-22_08-30-01`。
- [x] 主要な分岐が単体テストで確認されている
  - 検証結果: 指摘あり
  - 確認根拠: 再生成時の `validating -> running`、空回答本文、検証用user_id、HTML成果物リンク、リンク種別別拡張子のテストが不足。
- [x] 主要な外部境界が結合テストで確認されている
  - 検証結果: 指摘あり
  - 確認根拠: REST/SSE再表示とDB保存は確認されているが、チャット受付APIからF005実行が起動する結合契約が不足。issue `2026-06-22_08-30-01`。
- [x] テスト用fake/stubが本番契約を隠していない
  - 検証結果: 指摘あり
  - 確認根拠: `FakeValidatorCodexRunner` は `user_id` を観測しておらず、本番 `CodexRunner` の作業領域契約逸脱を隠している。issue `2026-06-22_08-30-03`。
- [x] coverage結果が品質ゲートを満たしている
  - 検証結果: 適合
  - 確認根拠: evidence上、単体95.74%、結合80.34%で門番値を満たす。

## 8. 修正方針

- [x] 指摘は実装修正で解消可能か確認した
  - 検証結果: 修正可能
  - 確認根拠: 5件とも実装・テスト追加で解消可能。仕様書側修正候補ではない。
- [x] 仕様書側修正が必要な項目を分離した
  - 検証結果: 該当なし
  - 確認根拠: 参照した設計間に大きな矛盾はなく、実装側が追従していない。
- [x] TBC候補があれば分類した
  - 検証結果: 該当なし
  - 確認根拠: 今回の指摘はいずれも既存docsで判断可能。
- [x] F005完了可否へ影響する指摘を分類した
  - 検証結果: 完了不可
  - 確認根拠: API受付からCodex実行が起動しない指摘はF005機能成立に直結する。
- [x] issueを1指摘1ファイルで作成した
  - 検証結果: 作成済み
  - 確認根拠: `.issue/implement-from-docs/2026-06-22_08-30-01` から `08-30-05` まで5件を作成した。

# API縦断MVP 結合契約マトリクス

| 契約ID | 対象 | 設計根拠 | 契約 | 状態 |
| --- | --- | --- | --- | --- |
| I-API-001 | `GET /api/app-config` | IF-SB-01、アプリ設定取得処理設計 | 歓迎メッセージと入力候補だけを返し、内部パスやDB URLを返さない。 | 結合テスト済み |
| I-API-002 | `POST /api/chats/start` | IF-SB-02、新規チャット開始処理設計 | 正常入力でチャット、run、指示を作成し、`chat_id`、`run_id`、`sse_url`、`受付` を返し、dispatcherへ登録する。 | 結合テスト済み |
| I-API-003 | `POST /api/chats/start` | IF-SB-02、新規チャット開始処理設計 | 空白だけの指示をHTTP 400で拒否し、部分保存を残さない。 | 結合テスト済み |
| I-API-004 | `POST /api/chats/{chat_id}/runs` | IF-SB-03、継続指示受付処理設計 | 終端済みrunだけの既存チャットへ継続runを追加できる。 | 結合テスト済み |
| I-API-005 | `POST /api/chats/{chat_id}/runs` | IF-SB-03、継続指示受付処理設計 | 未完了runがあるチャットへの継続指示をHTTP 409で拒否する。 | 結合テスト済み |
| I-API-006 | `GET /api/chat-histories` | IF-SB-04、履歴一覧取得処理設計 | 履歴を更新日時降順で返し、回答本文や中間メッセージ全文を含めない。 | 結合テスト済み |
| I-API-007 | `GET /api/chats/{chat_id}` | IF-SB-05、履歴詳細取得処理設計 | run、指示、中間メッセージ、回答、参照元を開始日時順で返す。 | 結合テスト済み |
| I-API-008 | `POST /api/chats/{chat_id}/runs/{run_id}/cancel` | IF-SB-07、キャンセル処理設計 | `受付` runをキャンセルし、HTTP応答は `キャンセル要求中` メッセージ、履歴詳細は `キャンセル済み` になる。 | 結合テスト済み |
| I-API-009 | `GET /api/chats/{chat_id}/runs/{run_id}/sse` | IF-SB-06、SSE購読処理設計 | 接続直後に現在状態を `state` イベントとして送信する。 | 結合テスト済み |
| I-API-010 | `GET /api/references/{reference_id}` | IF-SB-09、参照元PDF取得処理設計 | 保存済みPDF参照元だけを `application/pdf` で配信し、非PDF、許可外パス、実体なしを拒否する。 | 結合テスト済み |
| I-API-011 | `GET /api/artifacts/{artifact_id}` | IF-SB-08、Codex成果物配信処理設計 | 採用済み成果物だけを保存済みMIMEタイプで配信し、許可外MIMEと実体なしを拒否する。 | 結合テスト済み |
| I-API-012 | アプリ起動時回復 | 起動時実行回復処理設計 | 受付runは再登録対象、実行中/検証中はエラー、キャンセル要求中はキャンセル済みに整合する。 | 結合テスト済み |
| I-API-013 | `GET /api/chats/{chat_id}` | IF-SB-05、履歴詳細取得処理設計 | 対象チャットなしをHTTP 404で返す。 | 結合テスト済み |
| I-API-014 | 共通エラー変換 | エラー処理設計 | Repositoryのシステム例外をHTTP 500へ変換する。 | 結合テスト済み |
| I-API-015 | `GET /api/chats/{chat_id}/runs/{run_id}/sse` | IF-SB-06、SSE購読処理設計、SSEイベント配信IF | 接続直後の現在状態に続けて、購読した `state`、`message`、`answer`、`error` をSSE形式で配信する。 | 結合テスト済み |
| I-API-016 | 既定アプリ実行構成 | チャット実行処理設計、RunExecutionDispatcher IF、Codex実行IF、トレースログIF | `create_app()` の既定構成でRunEventBroker、InProcessRunExecutionDispatcher、生成/検証Codexアダプタ、成果物保存、トレースログを接続し、Fake Codex経由で回答保存まで到達する。 | 結合テスト済み |
| I-API-017 | REST/SSE/ファイル配信境界 | トレースログIF、ログ設計、参照元PDF取得処理設計、Codex成果物配信処理設計 | REST、SSE、参照元PDF配信、Codex成果物配信の開始・成功・失敗をtrace_idつきJSONLへ保存する。 | 結合テスト済み |
| I-API-018 | 既定アプリ実行構成 | Codex実行IF、設定ファイルIF、回答検証・再生成処理設計 | 既定DI経由で、生成用session `readonly/` に共有データソース、検証用session `readonly/` に共有データソースと回答候補が提示される。 | 結合テスト済み |
| I-API-019 | 既定アプリ実行構成 | Codex実行IF、チャット実行処理設計、SSEイベント配信IF | 既定DI経由で生成用CodexのJSONLイベント通知を受け取り、通常本文と安全なecho進捗出力を履歴詳細へ保存し、SSE配信対象のrunイベントとして扱う。最終回答の生成結果JSONは中間メッセージとして保存しない。 | 結合テスト済み |
| I-API-020 | 既定アプリ実行構成 | Codex実行IF、回答検証処理設計、SSEイベント配信IF | 既定DI経由で検証用CodexのJSONLイベント通知を受け取り、検証中間メッセージと安全なecho進捗出力を履歴詳細へ保存し、SSE配信対象のrunイベントとして扱う。 | 結合テスト済み |
| I-API-021 | 既定アプリ実行構成 | チャット実行処理設計、IF-SB-06、SSEイベント配信IF | 既定DI経由で生成・検証を実行したとき、システム固定の中間メッセージとCodex由来の中間メッセージが発生順で履歴詳細へ保存される。 | 結合テスト済み |
| I-API-022 | `GET /api/chats/{chat_id}/runs/{run_id}/sse` | IF-SB-06、SSEイベント配信IF | SSE接続前に保存済みの中間メッセージを、接続直後の `state` に続けて発生順で `message` 配信する。 | 結合テスト済み |
| I-API-023 | 既定アプリ実行構成 | Codex実行IF、チャット実行処理設計 | 検証用Codexが検証結果JSONをagent_messageとして出力しても、履歴詳細の中間メッセージには保存しない。生成用Codexの最終回答JSONも履歴詳細の中間メッセージには保存しない。 | 結合テスト済み |

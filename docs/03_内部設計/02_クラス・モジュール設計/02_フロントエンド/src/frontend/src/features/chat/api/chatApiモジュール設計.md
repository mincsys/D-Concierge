# chatApiモジュール設計

## 1. 文書の目的

本書は、`chatApi` モジュールの責務、不変条件、公開プロパティ、公開関数、および公開イベントを定義することを目的とする。

## 2. 前提

- 本書の対象は `モジュール一覧.md` で詳細設計対象とした `chatApi` モジュールのみとする。
- UIコンポーネントは `src/frontend/backend_mock/` を直接参照せず、本モジュール経由で `/api/...` と通信する。
- API応答のsnake_caseから画面モデルのcamelCaseへの変換は本モジュールが所有する。
- フロントエンド単体確認用モックを使う場合も、Vite middlewareが `/api/...` を応答し、本モジュールの通信境界は変えない。

## 3. 責務

- アプリ設定、履歴一覧、チャット詳細、新規チャット開始、継続指示、キャンセル、チャット削除のREST通信を提供する。
- チャット受付応答後、最新のチャット詳細を取得して画面モデルへ変換する。
- SSEを購読し、受信イベントを順序どおりに呼出元へ通知する。
- 終端イベント受信時点、旧ストリーム化、呼出元による購読解除、SSE接続異常に応じてEventSourceを閉じる。
- API応答データを `ChatHistoryItem`、`ChatSession`、`ChatRun`、`ChatAnswer` へ変換する。
- 削除受付応答を `DeleteChatResponse` へ変換する。
- APIエラー応答を、HTTPステータス、エラー分類、利用者向けメッセージを持つフロントエンド内部エラーへ変換する。

## 4. 不変条件

- REST通信はすべて `/api/...` パスに対して実行する。
- `src/frontend/backend_mock/` の固定データ、参照元、Codex成果物、疑似SSEを本モジュールから直接importしない。
- SSE終端イベントは `answer`、`error`、`canceled` のいずれかとし、終端後はEventSourceを閉じる。
- 終端イベント受信後に届いたSSEイベントは、呼出元へ通知しない。
- `isCurrent()` が `false` を返した後は、以降のSSEイベントを呼出元へ通知しない。
- `AbortSignal` による購読解除は正常終了として扱い、呼出元へSSE切断エラーを返さない。
- `startChat` と `appendChatRun` は、受付応答の `chat_id` を使ってチャット詳細を取得する。
- API変換後の画面モデルでは、参照元配列が欠落していても空配列として扱う。
- `deleteChat` は削除受付応答の `chat_state` が `deleting` であることを検証して返す。
- `deleteChat` は物理削除完了を待つ追加ポーリングを行わない。

## 5. 公開メソッド

| メソッド | 役割 | 入力 | 出力 | 事前条件 | 事後条件 |
| --- | --- | --- | --- | --- | --- |
| `getAppConfig` | アプリ設定を取得する | なし | 歓迎メッセージと入力候補 | `/api/app-config` がJSONを返すこと | API応答がそのまま返ること |
| `listChatHistories` | 履歴一覧を取得する | なし | 画面表示用履歴一覧 | `/api/chat-histories` が配列JSONを返すこと | 各履歴のID、タイトル、最新状態、更新日時が画面モデルへ変換されること |
| `getActiveChatSession` | 起動時に表示する直近チャットを取得する | なし | チャットセッション | 履歴一覧取得が成功すること | 履歴がある場合は先頭履歴の詳細を返すこと<br>履歴がない場合は空セッションを返すこと |
| `getChatDetail` | 指定チャット詳細を取得する | チャットID | チャットセッション | チャットIDが空でないこと | 実行履歴と回答が画面モデルへ変換されること |
| `startChat` | 新規チャット開始を受付する | 初回ユーザ指示 | 受付応答とチャットセッション | 指示本文をtrimした結果が空でないこと | 受付応答の `chat_id` に対応するチャット詳細が返ること |
| `appendChatRun` | 既存チャットへ継続指示を受付する | チャットID、継続指示 | チャットID、受付応答、チャットセッション | チャットIDが空でないこと<br>指示本文をtrimした結果が空でないこと | 受付応答の `chat_id` に対応するチャット詳細が返ること |
| `cancelChatRun` | 指定runのキャンセルを要求する | チャットID、run ID | キャンセル受付結果 | チャットIDとrun IDが空でないこと | 対象run ID、`cancel_requested` 状態、利用者向けメッセージが返ること |
| `deleteChat` | 指定チャットの削除を要求する | チャットID | `DeleteChatResponse` | チャットIDが空でないこと | `DELETE /api/chats/{chatId}` を呼び、`{ chatId, chatState: "削除中" }` を返すこと |
| `streamChatRun` | SSEを購読してイベントを順序処理する | SSE URL、現行ストリーム判定、イベントハンドラ、AbortSignal | 終端または中断までの完了Promise | SSE URLが空でないこと<br>イベントハンドラが例外を呼出元へ返せること | 終端イベント受信時点でEventSourceが閉じられること<br>終端イベントのイベントハンドラ完了後にPromiseが完了すること<br>旧ストリーム化または呼出元による購読解除は正常終了として扱うこと |
| `toChatHistoryItem` | 履歴API応答を画面モデルへ変換する | 履歴API応答1件 | 履歴画面モデル1件 | 入力にチャットID、タイトル、状態、更新日時があること | snake_case項目がcamelCaseへ変換されること |
| `toApiError` | APIエラー応答を内部エラーへ変換する | `Response` と応答JSON | HTTPステータス、エラー分類、メッセージを持つエラー | 応答JSONが `ErrorResponseSchema` 相当であること | 呼出元が削除中、削除済み、削除受付失敗を判定できること |

## 6. 公開イベント

| イベント名 | 発火条件 | 通知内容 |
| --- | --- | --- |
| `onEvent` | `streamChatRun` がSSEイベントを1件処理するとき | `state`、`message`、`answer`、`error`、`canceled` のいずれかのイベント |

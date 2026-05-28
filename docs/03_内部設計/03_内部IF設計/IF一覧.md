# IF一覧

## 1. 文書の目的

本書は、D-Conciergeで定義する内部IFを一覧化し、個別IF設計への入口を提供することを目的とする。

## 2. 前提

- 対象は、同一システム内のモジュール間API、application ports、イベント配信、ファイルアクセス、設定読込などの内部境界とする。
- 画面バックエンドAPI、codex exec CLI引数、設定ファイル項目そのものの外部向け仕様は外部設計書で扱い、本書では内部実装が利用する契約だけを扱う。
- 単純なReact props、private helper、型定義のみの境界は本書の詳細対象から除外する。

## 3. 収集対象

| 観点 | 方針 |
| --- | --- |
| 1 IF の単位 | レイヤ間または主要モジュール間で責務境界をまたぎ、入力、出力、例外、順序を契約化する必要がある単位 |
| 詳細ファイルへ展開する条件 | 副作用を伴う、非同期処理を伴う、状態整合性に影響する、複数実装へ差し替える可能性がある、または画面状態更新の基点となるIF |

## 4. IF一覧

| 区分 | IF名 | 呼出元 | 呼出先 | 目的 | 詳細ファイル |
| --- | --- | --- | --- | --- | --- |
| フロントエンド | チャットAPIクライアントIF | `ChatPage` | `chatApi` | 画面状態管理とREST/SSE通信、削除要求を分離する。 | [チャットAPIクライアントIF.md](チャットAPIクライアントIF.md) |
| バックエンド application port | AccountRepository IF | `application/account` | `application/ports/database/interface.py`、実装は `infrastructure/database/repositories` | ユーザ、ログインセッション、アカウント削除対象の永続化、状態更新、削除対象取得、トランザクション境界を抽象化する。 | [AccountRepositoryIF.md](AccountRepositoryIF.md) |
| バックエンド application port | チャットRepository IF | `application` | `application/ports/database/interface.py`、実装は `infrastructure/database/repositories` | チャット、run、指示、回答、参照元、成果物メタ情報の永続化、チャット状態更新、削除対象取得、トランザクション境界を抽象化する。 | [チャットRepositoryIF.md](チャットRepositoryIF.md) |
| バックエンド application/security | PasswordHasher IF | `application/account` | `application/ports/security/interface.py`、実装は `infrastructure/security` | パスワード生値のハッシュ化と、入力パスワードと保存済みハッシュの検証を抽象化する。 | [PasswordHasherIF.md](PasswordHasherIF.md) |
| バックエンド application/security | SessionTokenProvider IF | `application/account` | `application/ports/security/interface.py`、実装は `infrastructure/security` | ログインセッショントークンの発行と、DB保存用の照合ハッシュ生成を抽象化する。 | [SessionTokenProviderIF.md](SessionTokenProviderIF.md) |
| バックエンド application/runtime | RunExecutionDispatcher IF | `application/chat`、`app` | `application/ports/runtime/interface.py`、実装は `infrastructure/runtime` | 受付済みrunをバックグラウンド実行へ登録し、起動時に未完了runを整合させる。 | [RunExecutionDispatcherIF.md](RunExecutionDispatcherIF.md) |
| バックエンド application/runtime | ChatDeletionDispatcher IF | `application/chat`、`app` | `application/ports/runtime/interface.py`、実装は `infrastructure/runtime` | 削除対象チャットをバックグラウンド削除へ登録し、起動時に`deleting`のチャットを再登録する。 | [ChatDeletionDispatcherIF.md](ChatDeletionDispatcherIF.md) |
| バックエンド application/runtime | AccountDeletionDispatcher IF | `application/account`、`app` | `application/ports/runtime/interface.py`、実装は `infrastructure/runtime` | 削除対象ユーザをバックグラウンド削除へ登録し、起動時に`deleting`のユーザを再登録する。 | [AccountDeletionDispatcherIF.md](AccountDeletionDispatcherIF.md) |
| バックエンド application port | Codex実行IF | `application/execution`、`application/validation`、`application/chat`、`application/account` | `application/ports/codex/interface.py`、実装は `infrastructure/codex` | 生成用Codex実行、参照元検証、終了制御、作業領域解決、作業領域削除を抽象化する。 | [Codex実行IF.md](Codex実行IF.md) |
| バックエンド presentation/application | SSEイベント配信IF | `application/execution` | `presentation/sse` | run状態、中間メッセージ、回答、エラー、キャンセルをSSE購読者へ配信する。 | [SSEイベント配信IF.md](SSEイベント配信IF.md) |
| バックエンド application port | 成果物ファイルIF | `application/artifacts`、`application/chat`、`application/account` | `application/ports/filesystem/interface.py`、実装は `infrastructure/filesystem/file_artifact_store.py` | 採用済みCodex成果物の保存、配信用読込、保存済み成果物実体削除を抽象化する。 | [成果物ファイルIF.md](成果物ファイルIF.md) |
| バックエンド application port | 参照元ファイルIF | `application/references` | `application/ports/filesystem/interface.py`、実装は `infrastructure/filesystem/file_reference_store.py` | 保存済みPDF参照元の安全な取得を抽象化する。 | [参照元ファイルIF.md](参照元ファイルIF.md) |
| バックエンド application port | 設定読込IF | `app`、`presentation`、`application`、`infrastructure` | `infrastructure/config` | `config.yaml` の読込結果を型付き設定として提供する。 | [設定読込IF.md](設定読込IF.md) |
| バックエンド application port | Runtime Provider IF | `application` | `application/ports/runtime/interface.py`、実装は `infrastructure/runtime` | 現在時刻とID発番を差し替え可能にする。 | [RuntimeProviderIF.md](RuntimeProviderIF.md) |
| バックエンド application port | トレースログIF | `presentation`、`application` | `application/ports/trace_log/interface.py`、実装は `infrastructure/trace_log` | trace_id付きの異常系調査情報を1異常1YAMLファイルへ記録する。 | [トレースログIF.md](トレースログIF.md) |

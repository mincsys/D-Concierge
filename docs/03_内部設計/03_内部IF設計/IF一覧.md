# IF一覧

## 1. 文書の目的

本書は、D-Concierge MVPで定義する内部IFを一覧化し、個別IF設計への入口を提供することを目的とする。

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
| フロントエンド | チャットAPIクライアントIF | `ChatPage` | `chatApi` | 画面状態管理とREST/SSE通信を分離する。 | [チャットAPIクライアントIF.md](チャットAPIクライアントIF.md) |
| バックエンド application port | チャットRepository IF | `application` | `infrastructure/database/repositories` | チャット、run、指示、回答、参照元、成果物メタ情報の永続化を抽象化する。 | [チャットRepositoryIF.md](チャットRepositoryIF.md) |
| バックエンド application port | Codex実行IF | `application/execution`、`application/validation` | `infrastructure/codex` | 生成用/検証用codex execの起動、イベント取得、終了制御を抽象化する。 | [Codex実行IF.md](Codex実行IF.md) |
| バックエンド presentation/application | SSEイベント配信IF | `application/execution` | `presentation/sse` | run状態、中間メッセージ、回答、エラー、キャンセルをSSE購読者へ配信する。 | [SSEイベント配信IF.md](SSEイベント配信IF.md) |
| バックエンド application port | 成果物ファイルIF | `application/artifacts`、`application/validation` | `infrastructure/filesystem/artifacts` | 採用済みCodex成果物の検証、保存、配信用読込を抽象化する。 | [成果物ファイルIF.md](成果物ファイルIF.md) |
| バックエンド application port | 参照元ファイルIF | `application/references`、`application/validation` | `infrastructure/filesystem/references` | PDF参照元の安全な取得と検証用パス解決を抽象化する。 | [参照元ファイルIF.md](参照元ファイルIF.md) |
| バックエンド application port | 設定読込IF | `app`、`presentation`、`application`、`infrastructure` | `infrastructure/config` | `config.yaml` の読込結果を型付き設定として提供する。 | [設定読込IF.md](設定読込IF.md) |
| バックエンド application port | Runtime Provider IF | `application`、`domain` | `infrastructure/runtime` | 現在時刻とID発番を差し替え可能にする。 | [RuntimeProviderIF.md](RuntimeProviderIF.md) |
| バックエンド shared/application port | トレースログIF | `presentation`、`application` | `infrastructure/trace_log` | trace_id付きの処理開始、終了、例外、再生成、検証失敗をJSONLへ記録する。 | [トレースログIF.md](トレースログIF.md) |

# presentation層のRESTとエラー変換がapp factoryに集約されている

## 内容

`docs/03_内部設計/01_アーキテクチャ設計/アーキテクチャ設計.md` と `docs/03_内部設計/01_アーキテクチャ設計/ディレクトリ構成.md` では、`presentation/rest` がRESTエンドポイント実装、`presentation/errors` が例外からHTTP応答への変換を担い、`app` はFastAPIアプリの組み立てとルーティング登録を担う設計になっている。

一方、現行実装ではRESTエンドポイント、例外ハンドラ、SSEエンドポイント、配信用 `FileResponse` 生成の多くが `src/backend/app/factory.py` に集約されている。`presentation/rest` と `presentation/errors` の実装ファイルは存在しない。

さらに、`app/router` はREST/SSEエンドポイント登録処理の配置先として設計されているが、現行実装では空であり、router登録も `app/factory.py` 内のデコレータで行われている。

## 影響

composition rootである `app/factory.py` が、DIだけでなくAPI境界の責務も持っている。機能追加時にファイルが肥大化し、API契約・エラー変換・ユースケース組み立ての変更影響が分かりにくくなる。

## 設計と実装の評価

設計の方がよい。REST境界と例外変換はpresentation層へ分け、`app/factory.py` は依存関係の組み立てとrouter登録へ絞る方が責務が明確になる。

対応は、既存のルート関数を `presentation/rest` へ、`AppError` の例外変換を `presentation/errors` へ移し、`app/router` で登録する構成へ寄せる。すぐに全面移動しない場合でも、新規エンドポイントは設計どおりpresentation層へ追加する。

# SPA静的配信設定が実装されていない

## 内容

`docs/03_内部設計/01_アーキテクチャ設計/アーキテクチャ設計.md` では、`src/backend/app/static` がビルド済みSPAを配信する設定を保持すると定義されている。

`docs/03_内部設計/01_アーキテクチャ設計/ディレクトリ構成.md` でも、`src/backend/app/static/` は「静的配信設定」とされている。また、`docs/05_開発標準/01_環境構築/本番環境構築.md` では、`src/frontend/dist` を `src/backend/app/static/dist` へコピーする手順が記載されている。

一方、現行実装では `src/backend/app/static/` は空であり、`src/backend/app/factory.py` にも `StaticFiles` のmountやSPA fallbackの設定がない。

## 影響

本番環境構築書どおりにフロントエンドをビルドして `src/backend/app/static/dist` に配置しても、FastAPIバックエンド単体ではSPAを配信できない可能性がある。

開発時はVite dev serverで画面を表示できるため表面化しにくいが、本番構成や総合テストの前提と実装がずれている。

## 設計と実装の評価

設計の方がよい。D-Conciergeの本番構成でバックエンドがWeb画面配信も担う前提なら、ビルド済みSPA配信設定は実装すべきである。

対応は、`app/static` または `app/router` に静的配信設定を追加し、`dist` が存在する場合にFastAPIへmountする。APIルートと競合しないよう、`/api` 以外をSPA fallbackへ流すか、運用上別Webサーバで配信するなら設計書・環境構築書をその方式へ修正する。

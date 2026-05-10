# バックエンド結合テストがPostgreSQLを使用していない

## 内容

`docs/04_テスト/03_結合テスト/結合テスト方針.md` では、バックエンド結合テストはmigration適用後のPostgreSQLテストDBを使用する前提になっている。

一方、現在の `src/backend/tests/integration/test_api_vertical_mvp.py` は `InMemoryChatRepository` を `create_app` に注入しており、GitHub Actionsで起動している `postgres-test` へ接続していない。

## 影響

GitHub Actionsの成功可否には直ちに影響しないが、Repository、migration、PostgreSQL制約を含む結合確認になっていない。

## 対応方針

バックエンド結合テストをPostgreSQLテストDBへ接続する構成に改めるか、結合テスト方針書側で現在の境界テスト範囲に合わせて記載を修正する。

## 設計と実装の評価

設計の方がよい。結合テスト方針はRepository、migration、PostgreSQL制約、トランザクションを確認対象に含めており、実装が `InMemoryChatRepository` だけを使うと部分UNIQUE制約やJSONB CHECKなどの重要な不具合を検出できない。

対応は、現行テストの一部を軽量なAPI連携テストとして残す場合でも、少なくとも代表的なバックエンド結合テストはGitHub Actionsの `postgres-test` に接続して実DB経由にするのがよい。

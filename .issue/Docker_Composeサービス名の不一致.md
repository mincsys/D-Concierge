# Docker Composeサービス名の不一致

## 概要

`docs/00_設計メモ/技術構成と実行方式.md` の開発時起動例では、PostgreSQLだけを起動するコマンドとして `docker compose up db` が記載されている。

現行の `infra/compose.yml` ではサービス名が `postgres` と `postgres-test` であり、`db` サービスは定義されていない。

## 影響

環境構築書で設計メモのコマンドをそのまま採用すると、実行不能な手順になる。

## 対応方針

環境構築書では `infra/compose.yml` を正とし、開発用DBは `docker compose -f infra/compose.yml up -d postgres`、テスト用DBは `docker compose -f infra/compose.yml up -d postgres-test` を記載する。

設計メモを整理する場合は、`db` を `postgres` へ修正する。

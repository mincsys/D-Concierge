---
name: explore-d-concierge
description: readonly/d-concierge_codebase/D-Concierge にある D-Concierge 自身のコードベースと設計書を調査し、参照ファイルを明示して根拠付きで回答する。
---

# Explore D-Concierge

## 概要

`readonly/d-concierge_codebase/D-Concierge` にある D-Concierge の現行スナップショットを調査し、ユーザの質問に根拠付きで回答する。Git履歴は扱わず、現行ファイルの内容を正とする。

## 基本ルール

- 調査対象ルートは `readonly/d-concierge_codebase/D-Concierge`。
- readonly配下のファイルは編集しない。
- 調査には `rg`、`find`、`sed` などを使い、質問に近い `docs/`、`src/`、`tests/`、`.issue/` を絞り込む。
- Git履歴は扱わず、`git log` や `git show` は使わない。
- 回答の末尾に `参照ファイル` セクションを置き、参照したファイルを調査対象ルートからの相対パスで列挙する。
- 参照ファイルは `docs/02_外部設計/...`、`src/backend/...` のように書き、`readonly/d-concierge_codebase/D-Concierge/` は付けない。

## 探索順

- 要件・仕様の質問は `docs/01_要件定義`、`docs/02_外部設計` から確認する。
- 実装構造・責務の質問は `docs/03_内部設計` と `src/` を照合する。
- API、SSE、設定、Codex IF の質問は外部IF設計、内部IF設計、該当実装を確認する。
- テスト・CIの質問は `docs/04_テスト`、`.github/workflows`、`src/**/tests` を確認する。
- 未解決課題や既知の乖離は `.issue/` を確認する。

## 主要ディレクトリ

- `docs/`: 要件定義、外部設計、内部設計、テスト設計、開発標準。
- `src/backend/`: FastAPIバックエンド。
  - `app/`: アプリ生成、ルータ登録、静的ファイル配信。
  - `application/`: ユースケース、アプリケーションサービス、アプリケーション境界。
  - `domain/`: ドメインモデル、状態、ポリシー、値オブジェクト。
  - `infrastructure/`: Codex実行、設定読込、DB、ファイル、runtime、トレースログ。
  - `presentation/`: REST API、SSE、APIスキーマ、HTTPエラー変換。
  - `shared/`: 共通エラー、トレース、利用者向けメッセージ。
  - `tests/`: backendの単体・結合テストとテスト支援実装。
- `src/frontend/`: React/Viteフロントエンド。
  - `src/`: アプリ、コンポーネント、feature、ページ、スタイル。
  - `backend_mock/`: フロントエンド単体開発用のmock backend。
  - `tests/`: frontendの単体・結合テスト。
- `.github/workflows/`: GitHub ActionsのCI定義。
- `.issue/`: 設計・実装乖離や改善課題のメモ。
- `codex/`: Codex設定、生成用・検証用スキル、出力JSONスキーマ。
- `infra/`: Docker、Compose、Codex実行コンテナ関連。
- ルート設定ファイル群:
  - `AGENTS.md`
  - `config.example.yaml`
  - `pyproject.toml`
  - `uv.lock`
  - `alembic.ini`
  - `src/frontend/package.json`
  - `src/frontend/vite.config.ts`
  - `src/frontend/vitest.config.ts`

## docs/ 構成

`docs/` は、要件定義、外部設計、内部設計、テスト設計、開発標準を格納する。調査時は、ユーザ質問に最も近い工程の文書から読み、必要に応じて前後工程へ戻る。

### `docs/01_要件定義/`

- `要件定義.md`
- `将来構想要件定義.md`

### `docs/02_外部設計/`

- `01_システム構成/`
  - `システム概要.md`
  - `ソフトウェア構成.md`
  - `ネットワーク構成.md`
  - `ハードウェア構成.md`
- `02_業務設計/`
  - `業務一覧.md`
  - `〇〇フロー.md`
- `03_機能設計/`
  - `機能一覧.md`
- `04_画面設計/`
  - `画面一覧.md`
  - `〇〇画面.md`
  - `img/`
    - `〇〇画面.png`
- `05_論理データ設計/`
  - `論理データ設計.md`
- `06_外部インターフェース設計/`
  - `画面バックエンドAPI IF.md`
  - `codex exec IF.md`
  - `設定ファイル IF.md`
- `07_非機能設計/`
  - `非機能設計.md`
- `08_共通設計/`
  - `用語集.md`
  - `エラーメッセージ設計.md`
  - `チャット履歴・実行中表示設計.md`
  - `ログ設計.md`

### `docs/03_内部設計/`

- `01_アーキテクチャ設計/`
  - `アーキテクチャ設計.md`
  - `ディレクトリ構成.md`
- `02_クラス・モジュール設計/`
  - `01_バックエンド/`
    - `クラス一覧.md`
    - `src/backend/.../〇〇クラス設計.md`
  - `02_フロントエンド/`
    - `モジュール一覧.md`
    - `src/frontend/.../〇〇モジュール設計.md`
- `03_内部IF設計/`
  - `IF一覧.md`
  - `〇〇IF.md`
- `04_処理設計/`
  - `処理一覧.md`
  - `〇〇処理設計.md`
- `05_データ設計/`
  - `物理データ設計.md`
- `06_共通設計/`
  - `共通設計.md`

### `docs/04_テスト/`

- `01_静的テスト/`
  - `静的テスト方針.md`
- `02_単体テスト/`
  - `単体テスト方針.md`
- `03_結合テスト/`
  - `結合テスト方針.md`
- `04_総合テスト/`
  - `総合テスト方針.md`
  - `テスト仕様・結果/`
    - `〇〇テスト.md`

### `docs/05_開発標準/`

- `01_環境構築/`
  - `開発環境構築.md`
  - `本番環境構築.md`
- `02_コーディング規約/`
  - `コーディング規約.md`

## 回答形式

質問に直接答えたうえで、末尾に参照したファイルを列挙する。

```markdown
...

**参照ファイル**
- `docs/02_外部設計/...`
- `src/backend/...`
```

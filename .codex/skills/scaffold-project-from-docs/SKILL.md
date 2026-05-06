---
name: scaffold-project-from-docs
description: Read project documents under docs/ to identify the actual stack, execution environment, quality gates, and required tools, then create only the initial scaffold that the documents justify. Use when Codex needs to build a development scaffold from docs/01_要件定義, docs/02_外部設計, docs/03_内部設計, and docs/04_テスト, must present the required install list first, wait for explicit user approval before generating files, avoid assuming a fixed technology stack, and ask the user to run any sudo-required commands.
---

# Scaffold Project From Docs

## Overview

`docs/` を読んで案件ごとの技術スタック、実行環境、品質ゲート、必要ツールを把握し、その根拠で正当化できる初期スキャフォールドだけを作成する。最初に必要なインストール一覧を提示し、ユーザの明示許可があるまでファイル生成や依存導入を行わない。

## Workflow

### 1. 主要 6 文書を優先して読む

- 先に次の 6 文書を読む。
  - `docs/01_要件定義/01_要件定義書.md`
  - `docs/02_外部設計/01_システム構成/ソフトウェア構成.md`
  - `docs/03_内部設計/01_アーキテクチャ設計/ディレクトリ構成.md`
  - `docs/04_テスト/01_静的テスト/静的テスト方針.md`
  - `docs/04_テスト/02_単体テスト/単体テスト方針.md`
  - `docs/04_テスト/03_結合テスト/結合テスト方針.md`
- まずこの 6 文書だけで、次を把握する。
  - 実行環境
  - 主要ソフトウェア
  - 依存サービス
  - テスト種別
  - 品質ゲート
  - 起動や検証に必要なツール
- `docs/05_開発標準` は入力に含めない。存在しなくてよい前提で進める。

### 2. 必要な場合だけ補助資料を読む

- 主要 6 文書だけで一意に決まらない場合のみ、README、既存設定ファイル、環境変数サンプル、Docker/Compose、依存定義、既存ディレクトリ構成を補助的に読む。
- 補助資料を読んでも一意に決まらない項目は、推測で埋めず未確定事項として扱い、ユーザに確認する。
- docs と既存設定が競合する場合は、競合内容と判断保留理由を明示する。

### 3. 最初にインストール一覧を提示する

- スキャフォールド作成前に、必ず必要なインストール一覧を提示する。
- 一覧は Markdown の表または箇条書きで、少なくとも次を含める。
  - 項目名
  - 用途
  - 根拠文書
  - `sudo` 要否
  - ユーザ実行が必要かどうか
- 最初の応答は次の順にする。
  - 読み取った技術スタックと実行環境の要約
  - 必要なインストール一覧
  - 未確定事項
  - 許可依頼
- ユーザの明示許可があるまで、ファイル生成、依存導入、設定変更、コード生成を行わない。

### 4. `sudo` が必要な操作はユーザへ依頼する

- `sudo` が必要なインストールやシステム設定は、自分で実行しない。
- 必要なコマンドをそのまま提示し、何のために必要かを短く添えてユーザへ依頼する。
- `sudo` 操作が終わるまで、その前提に依存する生成処理へ進まない。

### 5. 許可後にスキャフォールドを生成する

- 許可後は、読み取れた事実だけを根拠に初期スキャフォールドを生成する。
- docs に明示された技術だけを対象にする。
- docs に明示がなく、README や既存設定でも補えない技術は前提に含めない。
- 技術固有ファイルは、その技術が docs から読み取れた場合だけ生成対象にする。
- CI 定義は docs または既存設定で基盤が明示された場合のみ生成対象に含める。明示がなければ CI は未生成にする。

### 6. 生成範囲を制御する

- 共通的に有用な最小構成だけは `assets/common-template/` を利用してよい。
- 共通テンプレートには、技術固定を生まない資材だけを含める。
  - `.gitignore`
  - `.editorconfig`
  - `.env.example`
  - 空ディレクトリ雛形
  - 証跡ディレクトリ雛形
- 特定技術向けの固定テンプレートや固定キーワード表は持ち込まない。
- 技術固有の構成は、都度 docs を読んで判断し、必要ならその場で作成する。

### 7. 判断不能な場合は止まる

- 次のいずれかに該当する場合は、生成を始めずに止まる。
  - 主要技術や実行基盤が一意に決まらない
  - docs 間で競合がある
  - 必須のインストール前提が未許可である
  - `sudo` 必須作業が未実施である
- 停止時は、未確定事項、競合内容、追加で必要な判断を短く整理して提示する。

## Reading Rules

- 技術スタックは事前定義済みキーワード抽出ではなく、文書全体の読解で判断する。
- 判断時は、技術名だけでなく、実行コマンド、設定ファイル名、テストコマンド、運用条件、依存関係からも根拠を取る。
- docs に書かれていることを優先し、既存設定ファイルは補助根拠として使う。
- docs に存在しない将来想定や好みの構成は追加しない。

## Output Rules

- ユーザへの説明、生成するコメント、補助文書は日本語で書く。
- 最初の許可待ちメッセージでは、生成予定のファイルを書き始めず、判断根拠と必要インストールの提示に集中する。
- スキャフォールド生成後は、何を docs 根拠で作成したか、何を未確定のため作成しなかったかを分けて報告する。

## Resources

- 読込順序: [references/fact-reading-order.md](references/fact-reading-order.md)
- 技術スタック把握の観点: [references/stack-identification-guide.md](references/stack-identification-guide.md)
- インストール一覧の提示要件: [references/install-list-checklist.md](references/install-list-checklist.md)
- 完成前の確認観点: [references/review-checklist.md](references/review-checklist.md)

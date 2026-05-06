---
name: write-requirements-docs
description: Create Japanese waterfall-style requirements definition documents under docs/ by organizing user requests, existing materials, and discovered constraints. Use when Codex needs to elicit, structure, and write a requirements document from rough ideas, business requests, meeting notes, or partial specifications, especially when the output should cover system overview, scope, business requirements, functional requirements, screen requirements, data requirements, external integrations, non-functional requirements, and operational constraints in a formal requirements-definition format.
---

# Write Requirements Docs

## Overview

要望、既存資料、制約条件を整理し、日本語のウォーターフォール向け要件定義書を `docs/` 配下に作成する。聞き取り、要件の章立て、スコープ確定、要求の言語化、整合性確認を一体で扱う。

## Workflow

### 1. 既存情報を先に読む

- 先に `docs/` 配下、`AGENTS.md`、README、既存仕様書、議事メモを読む。
- 既存の要件定義書や関連文書がある場合は、文体、章立て、用語、ID体系を合わせる。
- ユーザがフォーマットや文書名を指定している場合は、その指示を最優先にする。
- 要件定義書の標準構成は [references/requirements-structure.md](references/requirements-structure.md) を基準にする。

### 2. 先に聞くべき論点を整理する

- 要件定義では推測で埋めすぎず、後続の設計や実装に影響する曖昧点を優先して確認する。
- 次の論点は優先的に固める。
  - 背景、目的、解決したい課題
  - 利用者区分、利用シーン、対象業務
  - 初期リリース範囲と対象外
  - 主要機能、画面、データ、外部連携
  - 性能、信頼性、運用制約、前提環境
- 聞く順番と代表論点は [references/elicitation-checklist.md](references/elicitation-checklist.md) を使う。

### 3. 要件定義書へ落とす

- 文書は日本語で書く。
- 章ごとに「何を決めたか」が明確になるよう、要件を断定形で書く。
- 設計や実装の解法ではなく、利用者要求、業務要求、システム要求として表現する。
- 差分説明や検討メモではなく、完成済みの正式文書として記述する。
- 図が有効な場合だけ `mermaid` を使い、背景、業務フロー、システム全体像の理解補助に留める。

### 4. 章間整合を揃える

- システム概要、開発対象範囲、業務要件、機能要件、画面要件、データ要件、外部連携要件、非機能要件、運用要件・制約の間で矛盾を残さない。
- 画面要件に出る画面は、機能要件や業務フローとつながるようにする。
- データ要件に出る主要データは、機能要件や外部連携要件と対応付くようにする。
- 最後に [references/review-checklist.md](references/review-checklist.md) で横断確認する。

## Writing Rules

- 文体は、ウォーターフォール開発向けの正式文書として簡潔で断定的にする。
- 「〜できること」「〜すること」を使い、要求事項を曖昧にぼかさない。
- 業務要件は利用者や管理者の行動で書き、機能要件はシステムの提供機能で書く。
- 非機能要件は、性能、操作性、信頼性、セキュリティ、運用制約を漏らさない。
- 実装方式を固定してよいか不明な場合は、まず要求レベルに留め、必要なときだけユーザに確認する。

## Resources

- 要件定義書の標準章立て: [references/requirements-structure.md](references/requirements-structure.md)
- 聞き取り論点と確認順序: [references/elicitation-checklist.md](references/elicitation-checklist.md)
- 完成前の横断点検: [references/review-checklist.md](references/review-checklist.md)

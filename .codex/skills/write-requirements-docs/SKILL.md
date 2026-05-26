---
name: write-requirements-docs
description: Create Japanese waterfall-style requirements definition documents under docs/ by organizing existing requirements documents, user requests, existing materials, and discovered constraints. Use when Codex needs to elicit, structure, agree, and write a requirements document from rough ideas, business requests, meeting notes, partial specifications, or existing requirements updates, especially when the output should cover system overview, scope, business requirements, functional requirements, screen requirements, data requirements, external integrations, non-functional requirements, operational constraints, one-question-at-a-time clarification, agreement summaries, and explicit start approval.
---

# Write Requirements Docs

## Overview

既存要件定義書、ユーザ指示、既存資料、制約条件を整理し、日本語のウォーターフォール向け要件定義書を `docs/` 配下に作成する。聞き取り、要件の章立て、スコープ確定、要求の言語化、合意結果の確認、整合性確認を一体で扱う。

## Workflow

### 1. 既存情報を先に読む

- 先に `docs/` 配下、`AGENTS.md`、README、既存仕様書、議事メモを読む。
- 既存の要件定義書がある場合は、それを主入力として扱う。
- ユーザから追加指示がある場合は、既存要件定義書への追加入力として扱う。
- 既存の要件定義書がない場合は、ユーザ要望、業務依頼、議事メモ、既存資料を入力として聞き取りを始める。
- 既存の要件定義書や関連文書がある場合は、文体、章立て、用語、ID体系を合わせる。
- 既存要件定義書、ユーザ指示、既存資料、README、モックが衝突する場合は、後続の設計や実装に影響する箇所を固定せず質問対象にする。
- ユーザがフォーマットや文書名を指定している場合は、その指示を最優先にする。
- 要件定義書の標準構成は [references/requirements-structure.md](references/requirements-structure.md) を基準にする。

### 2. 先に聞くべき論点を整理する

- 要件定義では推測で埋めすぎず、後続の設計や実装に影響する曖昧点を優先して確認する。
- `references/question-checklist.md` を使い、入力資料と衝突確認、背景・目的、利用者・利用シーン、スコープ、業務、機能、画面、データ、外部連携、非機能、運用要件・制約、実装へ踏み込む判断、作成対象ファイルを確認する。
- 次の論点は優先的に固める。
  - 背景、目的、解決したい課題
  - 利用者区分、利用シーン、対象業務
  - 初期リリース範囲と対象外
  - 主要機能、画面、データ、外部連携
  - 性能、信頼性、運用制約、前提環境
- 質問はまとめて行わず、必ず 1 つずつ順番に行う。
- 選択肢を提示する場合は、採用時の影響が明確に異なるものだけを Markdown の番号付きリストで示し、ユーザが番号だけで回答できることを明記する。
- 選択肢番号は質問ごとに `1` から始め、複数質問をまたいで連番にしない。
- 選択肢を提示する場合は、必ず推奨選択肢を 1 つだけ `1. 選択肢名（推奨）` のように明示し、推奨理由を簡潔に添える。
- 選択肢に `など`、`等`、`その他いろいろ` のような曖昧な表現を使わない。

### 3. 本文作成直前に合意状況を再確認する

- 要件定義書本文を作成する直前に、`references/question-checklist.md` の項目を `合意済み`、`未合意`、`リポジトリ事実として確定` のいずれかで整理する。
- 合意結果一覧には `質問項目`、`合意結果`、`状態`、`根拠` を含める。
- `合意済み` の根拠には、ユーザがどの回答で合意したかを書く。
- `リポジトリ事実として確定` の根拠には、どのファイル、設定、資料から一意に判断したかを書く。
- `未合意` の根拠には、何が未回答または未確定かを書く。
- 未合意項目がある場合は、要件定義書本文の作成へ進まない。
- 合意結果一覧をユーザへ表示した後、ユーザから明確な作成指示を受けるまで本文作成へ進まない。
- 明確な作成指示の例は、`作成してください`、`この内容で作成してください`、`本文作成に進んでください` とする。
- `確認しました`、`OKです`、`問題ありません` だけでは、作成開始指示とは扱わない。

### 4. 要件定義書へ落とす

- 文書は日本語で書く。
- 章ごとに「何を決めたか」が明確になるよう、要件を断定形で書く。
- 設計や実装の解法ではなく、利用者要求、業務要求、システム要求として表現する。
- 差分説明や検討メモではなく、完成済みの正式文書として記述する。
- 図が有効な場合だけ `mermaid` を使い、背景、業務フロー、システム全体像の理解補助に留める。

### 5. 章間整合を揃える

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
- 合意できていない前提を本文へ持ち込む場合は、ユーザが明示的にその進め方を指示したときに限る。

## Resources

- 要件定義書の標準章立て: [references/requirements-structure.md](references/requirements-structure.md)
- 質問チェックリスト: [references/question-checklist.md](references/question-checklist.md)
- 完成前の横断点検: [references/review-checklist.md](references/review-checklist.md)

---
name: teach-me
description: Use only when the user explicitly invokes teach-me or directly asks to use this skill; do not use it implicitly. Guides codebase learning through repository discovery, curriculum planning, and adaptive one-question-at-a-time quizzes.
---

# Teach Me

## Overview

作業ディレクトリ上のコードベースを調査し、ユーザの理解負債を減らすための対話型学習セッションを運営する。ドキュメントは補助資料として扱い、正解と説明は実装を主根拠にする。

## Workflow

### 1. 最初に調査する

- 学習を始める前に [references/discovery-checklist.md](references/discovery-checklist.md) を読み、作業ディレクトリ上のコード、ドキュメント、設定、テストを調査する。
- 構造把握や呼び出し関係の確認には、利用可能なら CodeGraph を優先する。文字列、文言、ログ、設定値などの literal 確認には `rg` やファイル読みを使う。
- 正しい問題と正解を作れる自信がない領域では、出題前または回答中に追加調査してから続ける。
- ドキュメントと実装がずれている可能性がある場合は、正解判定を保留せず、実装を主根拠にして説明する。

### 2. 学習範囲を一問一答で決める

- ユーザが学習テーマを指定していない場合は、[references/topic-selection.md](references/topic-selection.md) を読み、最初に学習レベルを番号付き選択肢で 1 問だけ質問する。必要な場合は、その次の質問で機能別候補を提示する。
- 選択肢には必ず `全範囲` と `自由回答` を含める。
- 質問は必ず一問一答形式にする。複数の確認事項を同時に聞かない。
- 初回案内で、専門用語が多く難しい場合は分かりやすい表現に変えられること、文章回答の割合を指定できること、未指定なら文章回答を約 30% にすることを伝える。

### 3. カリキュラムを作る

- 学習テーマが決まったら [references/curriculum-rules.md](references/curriculum-rules.md) を読み、詳細なカリキュラムを作成して提示する。
- 特に指定がない限り、正常系から始め、準正常系、異常系、変更影響、危険個所へ進める。
- 最初は広く浅く問い、理解度が見えた領域から徐々に深くする。
- 観点には、ドメイン理解、モジュール責務、データフロー、処理フロー、境界と依存、変更容易性、危険個所を含める。

### 4. 専門用語理解を診断する

- 教材としての最初の質問は、一般的な専門用語とプロジェクト固有用語をどの程度理解しているかを測る問題にする。
- 診断問題を数問続け、ユーザの回答に応じて、説明文を専門用語を含んだ厳密な表現にするか、噛み砕いた表現にするかを調整する。
- ユーザが表現レベルを指定した場合は、その指定を優先する。

### 5. 出題して採点する

- 出題時は [references/quiz-rules.md](references/quiz-rules.md) を読む。
- 採点時や深掘り時は [references/grading-rubric.md](references/grading-rubric.md) を読む。
- 多肢選択は原則 4 択にし、正解番号は毎回ランダムに変える。
- 誤選択肢は、似た責務、似た処理名、実装で起きそうな誤解、文書だけ読んだ場合に起きる誤解から作る。明らかに違う選択肢やひっかけ問題は作らない。
- 文章回答は指定割合に従う。未指定なら約 30% にする。
- 回答があやふやな場合は、そこを突っ込んで 1 問だけ深掘り質問をする。
- 誤答時は分かりやすく説明し、確認クイズを 1 問だけ出す。
- 2 回連続で誤答した場合、または理解が怪しい回答が続く場合は、簡単な問題に切り替える。3 回連続で正解した場合は、より深い問題へ進める。

### 6. 補足と要約を行う

- ユーザ回答後に、必要に応じて「実装上の事実」と「ドキュメント上の記述」を分けて補足する。
- プロジェクト指示で仕様と実装の乖離メモ作成が求められている場合は、その指示に従う。
- セッションの節目では [references/session-summary-format.md](references/session-summary-format.md) を読み、理解済み、要復習、誤解あり、未学習、次回候補を短く要約する。

## Resources

- 初期調査: [references/discovery-checklist.md](references/discovery-checklist.md)
- 学習範囲選択: [references/topic-selection.md](references/topic-selection.md)
- カリキュラム設計: [references/curriculum-rules.md](references/curriculum-rules.md)
- 出題ルール: [references/quiz-rules.md](references/quiz-rules.md)
- 採点と難易度調整: [references/grading-rubric.md](references/grading-rubric.md)
- セッション要約: [references/session-summary-format.md](references/session-summary-format.md)

import type { ChatHistoryItem, ChatSession } from "@/features/chat/model/types";

export const stubChatHistories: ChatHistoryItem[] = [
  { id: "requirements-success", title: "要件定義を成功させるポイント" },
  { id: "ipa-publication-qa", title: "IPA刊行物QA" },
  { id: "requirements-key-items", title: "要件定義の肝どころ" },
  { id: "sec-books-structure", title: "SEC BOOKS 構成検索" },
  { id: "pdf-reference-link", title: "PDF相関リンク設計" },
  { id: "codex-exec-json", title: "Codex exec JSON設計" },
  { id: "agentic-search-comparison", title: "Agentic Search比較" },
  { id: "systemization-plan", title: "システム化計画の進め方" },
  { id: "non-functional-requirements", title: "非機能要件の整理方法" },
  { id: "development-process-guide", title: "開発プロセス選定ガイド" },
  { id: "test-view-items", title: "テスト観点の洗い出し" },
  { id: "rfp-checklist", title: "RFP作成のチェックリスト" },
];

export const stubChatSession: ChatSession = {
  id: "requirements-success",
  userMessage: {
    id: "message-user-1",
    role: "user",
    text: "要件定義を成功させるポイントをIPA資料から整理して",
  },
  thoughtSteps: [
    { id: "keyword", text: "検索キーワードを整理します。" },
    { id: "search", text: "関連資料を検索します。" },
    { id: "locate", text: "各資料の要点・要約から該当箇所を特定します。" },
    { id: "html", text: "構造化HTML編集を実行します。" },
    { id: "quotes", text: "quotes表（キーワード一致）を実行します。" },
    { id: "summary", text: "要約・参照元の生成を行います。" },
  ],
  answer: {
    blocks: [
      {
        id: "requirements-items",
        markdown: `IPA資料から、要件定義を成功させるためのポイントを以下の通り整理します。

1. **目的・背景の共有と合意形成を徹底する。**  
   要件定義では目的や背景を共有し、関係する組織や役割を明確にすることが合意形成の第一歩です。
2. **利用者視点で要求を具体化する。**  
   利用者の業務や課題を深く理解し、価値につながる要求として具体化します。
3. **要求の優先順位付けとスコープ調整を行う。**  
   すべての要求を実装するのではなく、ビジネス価値と実現性のバランスで優先順位を付けます。

## 要件定義ワークフロー

\`\`\`mermaid
sequenceDiagram
  actor User as 利用者
  participant UI as D-Concierge UI
  participant Codex as Codex exec
  participant Skills as Skills
  participant Docs as 構造化Markdown/PDF

  User->>UI: 質問を送信
  UI->>Codex: AGENTS.mdと出力スキーマを指定して実行
  Note over UI,Codex: 中間メッセージを逐次表示
  loop 参照元候補の探索
    Codex->>Skills: 検索・grep・構造化Markdown検索
    Skills->>Docs: キーワード、章節、ページ範囲を照合
    Docs-->>Skills: 候補本文と位置情報を返却
    Skills-->>Codex: 参照元候補を返却
  end
  Codex->>Codex: 回答Markdownと参照元JSONを生成
  alt 参照元検証に成功
    Codex-->>UI: 回答ブロックと参照元リンクを返却
    UI-->>User: Markdown、Mermaid、HTML表、PDFリンクを表示
  else 参照元検証に失敗
    Codex-->>UI: 検証エラーを返却
    UI-->>User: 再実行またはエラーを表示
  end
\`\`\`

## 分析イメージ

![資料検索と参照元確認の分析イメージ](/artifacts/analysis-flow.svg)`,
        references: [
          {
            id: "sec-books-iot-guide-10-14",
            title: "SEC BOOKS 開発指針手引き",
            url: "/reference-pdf/iot-guide.pdf",
            startPage: 10,
            endPage: 14,
          },
          {
            id: "sec-books-iot-guide-20-22",
            title: "SEC BOOKS 開発指針手引き",
            url: "/reference-pdf/iot-guide.pdf",
            startPage: 20,
            endPage: 22,
          },
        ],
      },
      {
        id: "markdown-list-and-table",
        markdown: `## 箇条書きとMarkdown表の表示例

次の観点を確認すると、要件定義の抜け漏れを見つけやすくなります。

- 関係者、利用者、運用者の役割が明確になっている。
- 業務課題、期待効果、制約条件が同じ文脈で整理されている。
- 参照元ページと回答内容の対応を後から確認できる。

| 確認観点 | 確認する内容 | 状態 |
| --- | --- | --- |
| 目的共有 | 関係者が同じゴールを見て判断できる。 | 対応済み |
| 要求具体化 | 利用者の業務課題を検証可能な要求へ落とし込む。 | 対応済み |
| 参照元確認 | 回答ブロックごとに参照元リンクを確認できる。 | 対応済み |`,
        references: [
          {
            id: "sec-books-iot-guide-markdown-table-10-14",
            title: "SEC BOOKS 開発指針手引き",
            url: "/reference-pdf/iot-guide.pdf",
            startPage: 10,
            endPage: 14,
          },
        ],
      },
      {
        id: "requirements-html-table",
        markdown: `## HTML表の表示例

<table>
  <thead>
    <tr>
      <th rowspan="2">成功ポイント</th>
      <th colspan="2">確認内容</th>
      <th colspan="2">参照元</th>
    </tr>
    <tr>
      <th>要件定義での意味</th>
      <th>確認観点</th>
      <th>資料</th>
      <th>ページ</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">目的共有</th>
      <td>関係者が同じゴールを見て判断できる状態を作る。</td>
      <td>背景、目的、対象範囲が同じ言葉で説明されているか。</td>
      <td rowspan="2">SEC BOOKS 開発指針手引き</td>
      <td>PDF p.10-14</td>
    </tr>
    <tr>
      <th scope="row">要求の具体化</th>
      <td>利用者の業務課題を、検証可能な要求に落とし込む。</td>
      <td>利用者の行動、入力、期待結果が具体化されているか。</td>
      <td>PDF p.10-14</td>
    </tr>
    <tr>
      <th scope="row">継続的な見直し</th>
      <td>環境変化に合わせて、要求と合意内容を更新する。</td>
      <td>変更時の確認手順と関係者への共有方法が決まっているか。</td>
      <td>SEC BOOKS 開発指針手引き</td>
      <td>PDF p.20-22</td>
    </tr>
  </tbody>
</table>

※ 上記はIPA公開資料をもとに作成した要約です。詳細は参照元PDFをご確認ください。`,
        references: [
          {
            id: "sec-books-iot-guide-table-10-14",
            title: "SEC BOOKS 開発指針手引き",
            url: "/reference-pdf/iot-guide.pdf",
            startPage: 10,
            endPage: 14,
          },
        ],
      },
    ],
  },
  composerPlaceholder: "質問を入力してください（例：資料の要点を教えて、比較表を作って、など）",
};

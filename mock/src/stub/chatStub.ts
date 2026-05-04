import type { ChatHistoryItem, ChatSession } from "@/features/chat/model/types";

export const stubChatHistories: ChatHistoryItem[] = [
  { id: "requirements-success", title: "要件定義を成功させるポイント" },
  { id: "ipa-publication-qa", title: "IPA刊行物QA" },
  { id: "requirements-key-points", title: "要件定義の肝どころ" },
  { id: "sec-books-structure", title: "SEC BOOKS 構成検索" },
  { id: "pdf-reference-link", title: "PDF相関リンク設計" },
  { id: "codex-exec-json", title: "Codex exec JSON設計" },
  { id: "agentic-search-comparison", title: "Agentic Search比較" },
  { id: "systemization-plan", title: "システム化計画の進め方" },
  { id: "non-functional-requirements", title: "非機能要件の整理方法" },
  { id: "development-process-guide", title: "開発プロセス選定ガイド" },
  { id: "test-viewpoints", title: "テスト観点の洗い出し" },
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
    intro: "IPA資料から、要件定義を成功させるためのポイントを以下の通り整理します。",
    points: [
      {
        id: "shared-purpose",
        title: "目的・背景の共有と合意形成を徹底する。",
        description:
          "要件定義では目的や背景を共有し、関係する組織や役割を明確にすることが合意形成の第一歩です。",
        referenceLabel: "SEC BOOKS 開発指針手引き p.10",
      },
      {
        id: "user-perspective",
        title: "利用者視点で要求を具体化する。",
        description: "利用者の業務や課題を深く理解し、価値につながる要求として具体化します。",
        referenceLabel: "SEC BOOKS 開発指針手引き p.10",
      },
      {
        id: "prioritization",
        title: "要求の優先順位付けとスコープ調整を行う。",
        description:
          "すべての要求を実装するのではなく、ビジネス価値と実現性のバランスで優先順位を付けます。",
        referenceLabel: "SEC BOOKS 開発指針手引き p.10",
      },
    ],
    workflowTitle: "要件定義ワークフロー",
    imageTitle: "分析イメージ",
    htmlTitle: "HTML表の表示例",
    html: `
      <table class="answer-table">
        <thead>
          <tr>
            <th>成功ポイント</th>
            <th>要件定義での意味</th>
            <th>参照元</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>目的共有</td>
            <td>関係者が同じゴールを見て判断できる状態を作る。</td>
            <td>PDF p.10</td>
          </tr>
          <tr>
            <td>要求の具体化</td>
            <td>利用者の業務課題を、検証可能な要求に落とし込む。</td>
            <td>PDF p.10</td>
          </tr>
          <tr>
            <td>継続的な見直し</td>
            <td>環境変化に合わせて、要求と合意内容を更新する。</td>
            <td>PDF p.10</td>
          </tr>
        </tbody>
      </table>
    `,
    note: "※ 上記はIPA公開資料をもとに作成した要約です。詳細は参照元PDFをご確認ください。",
  },
  composerPlaceholder: "質問を入力してください（例：資料の要点を教えて、比較表を作って、など）",
};

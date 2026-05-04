import type { AnswerPoint } from "./types";

export const histories = [
  "要件定義を成功させるポイント",
  "IPA刊行物QA",
  "要件定義の肝どころ",
  "SEC BOOKS 構成検索",
  "PDF相関リンク設計",
  "Codex exec JSON設計",
  "Agentic Search比較",
  "システム化計画の進め方",
  "非機能要件の整理方法",
  "開発プロセス選定ガイド",
  "テスト観点の洗い出し",
  "RFP作成のチェックリスト",
];

export const thoughtLines = [
  "検索キーワードを整理します。",
  "関連資料を検索します。",
  "各資料の要点・要約から該当箇所を特定します。",
  "構造化HTML編集を実行します。",
  "quotes表（キーワード一致）を実行します。",
  "要約・参照元の生成を行います。",
];

export const answerPoints: AnswerPoint[] = [
  {
    title: "目的・背景の共有と合意形成を徹底する。",
    description:
      "要件定義では目的や背景を共有し、関係する組織や役割を明確にすることが合意形成の第一歩です。",
    referenceLabel: "SEC BOOKS 開発指針手引き p.10",
  },
  {
    title: "利用者視点で要求を具体化する。",
    description: "利用者の業務や課題を深く理解し、価値につながる要求として具体化します。",
    referenceLabel: "SEC BOOKS 開発指針手引き p.10",
  },
  {
    title: "要求の優先順位付けとスコープ調整を行う。",
    description:
      "すべての要求を実装するのではなく、ビジネス価値と実現性のバランスで優先順位を付けます。",
    referenceLabel: "SEC BOOKS 開発指針手引き p.10",
  },
];

export const answerTableHtml = `
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
`;

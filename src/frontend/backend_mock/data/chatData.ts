import type {
  AppConfigResponse,
  ChatDetailResponse,
  ChatHistoryResponseItem,
  SseEvent,
} from "../../src/features/chat/model/types";

export const stubAppConfig: AppConfigResponse = {
  welcome_message: "何なりとお申し付けください",
  input_suggestions: [
    "IPA資料の要点を整理して",
    "要件定義の観点を整理して",
    "SEC BOOKSを検索して",
    "PDFの参照元を明示して比較して",
  ],
};

export const stubChatHistories: ChatHistoryResponseItem[] = [
  {
    chat_id: "1c1f6f9a-4b1a-4f8e-91a0-62e6d62c0d10",
    title: "要件定義を成功させるポイント",
    latest_run_id: "4e5e7e31-2dd6-47b8-a2e2-3c58a2a2e381",
    latest_state: "completed",
    updated_at: "2026-05-08T01:00:00.000Z",
  },
  {
    chat_id: "2778fdaf-d3bf-42f9-9869-1939e2cd0a01",
    title: "IPA刊行物QA",
    latest_run_id: "c4b449ea-7e45-4e41-8888-fd2d973190ef",
    latest_state: "completed",
    updated_at: "2026-05-07T08:35:00.000Z",
  },
  {
    chat_id: "0dfb837f-c3cf-4d3c-9219-bf1c4f7fd2e7",
    title: "要件定義の肝どころ",
    latest_run_id: "3e0377eb-4c3d-4086-9fb0-3e448a84e846",
    latest_state: "completed",
    updated_at: "2026-05-06T05:18:00.000Z",
  },
  {
    chat_id: "c76ced7f-0192-4fc9-90a4-1091441f5cde",
    title: "公開資料の構成検索",
    latest_run_id: "47b5f723-8919-462b-9f16-7c7934dcaa62",
    latest_state: "completed",
    updated_at: "2026-05-05T02:20:00.000Z",
  },
  {
    chat_id: "a2064873-8c32-45ab-8853-1b90bd454fb7",
    title: "PDF相関リンク設計",
    latest_run_id: "9e59d303-3ad9-43e6-8de2-8c69424b1630",
    latest_state: "completed",
    updated_at: "2026-05-04T00:40:00.000Z",
  },
];

export const stubChatDetails: Record<string, ChatDetailResponse> = {
  "1c1f6f9a-4b1a-4f8e-91a0-62e6d62c0d10": {
    chat_id: "1c1f6f9a-4b1a-4f8e-91a0-62e6d62c0d10",
    title: "要件定義を成功させるポイント",
    runs: [
      {
        run_id: "d3a8f7cb-0e7c-4129-8730-52b94dfdbb1f",
        state: "completed",
        user_instruction: "要件定義を成功させるポイントをIPA資料から整理して",
        intermediate_messages: [
          { text: "検索キーワードを整理します。" },
          { text: "関連資料を検索します。" },
          { text: "各資料の要点・要約から該当箇所を特定します。" },
          { text: "参照元候補を検証します。" },
        ],
        answer: {
          blocks: [
            {
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
  participant Codex as 生成用codex exec
  participant Skills as Skills
  participant Docs as 構造化Markdown/PDF

  User->>UI: ユーザ指示を送信
  UI->>Codex: AGENTS.mdと出力スキーマを指定して実行
  Note over UI,Codex: 中間メッセージを逐次表示
  loop 参照元候補の探索
    Codex->>Skills: 検索・grep・構造化Markdown検索
    Skills->>Docs: キーワード、章節、ページ範囲を照合
    Docs-->>Skills: 候補本文と位置情報を返却
    Skills-->>Codex: 参照元候補を返却
  end
  Codex->>Codex: 回答Markdownと参照元JSONを生成
  Codex-->>UI: 回答と参照元リンクを返却
  UI-->>User: Markdown、Mermaid、HTML表、PDFリンクを表示
\`\`\`

## 分析イメージ

![資料検索と参照元確認の分析イメージ](/api/artifacts/6a9158c3-ae1c-4a13-9494-940df193ceef)`,
              references: [
                {
                  source_type: "pdf",
                  label: "SEC BOOKS 開発指針手引き",
                  url: "/api/references/9052af11-89cc-4273-bd2d-ad310805c442",
                  locator: {
                    page_start: 10,
                    page_end: 10,
                  },
                },
                {
                  source_type: "pdf",
                  label: "SEC BOOKS 開発指針手引き",
                  url: "/api/references/0125bb8d-cd63-4f12-8ce8-55a20b82d1e5",
                  locator: {
                    page_start: 20,
                    page_end: 22,
                  },
                },
              ],
            },
          ],
        },
      },
      {
        run_id: "4e5e7e31-2dd6-47b8-a2e2-3c58a2a2e381",
        state: "completed",
        user_instruction: "回答表示で表、コードブロック、HTML表も確認できる形にして",
        intermediate_messages: [
          { text: "前回の文脈を引き継いで表示要素を整理します。" },
          { text: "Markdown表、HTML表、コードブロックの表示例を作成します。" },
        ],
        answer: {
          blocks: [
            {
              markdown: `## 箇条書きとMarkdown表の表示例

次の観点を確認すると、要件定義の抜け漏れを見つけやすくなります。

- 関係者、利用者、運用者の役割が明確になっている。
- 業務課題、期待効果、制約条件が同じ文脈で整理されている。
- 参照元ページと回答内容の対応を後から確認できる。

| 確認観点 | 確認する内容 | 状態 |
| --- | --- | --- |
| 目的共有 | 関係者が同じゴールを見て判断できる。 | 対応済み |
| 要求具体化 | 利用者の業務課題を検証可能な要求へ落とし込む。 | 対応済み |
| 参照元確認 | 回答ごとに参照元リンクを確認できる。 | 対応済み |

## HTML表の表示例

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
  </tbody>
</table>

## コードブロックの表示例

\`\`\`json
{
  "answer": {
    "markdown": "参照元を確認しながら回答します。",
    "references": [
      {
        "source_type": "pdf",
        "label": "SEC BOOKS 開発指針手引き",
        "locator": {
          "page_start": 10,
          "page_end": 14
        }
      }
    ]
  }
}
\`\`\``,
              references: [
                {
                  source_type: "pdf",
                  label: "SEC BOOKS 開発指針手引き",
                  url: "/api/references/f326ba99-872d-4c64-89b5-cadf41874f20",
                  locator: {
                    page_start: 10,
                    page_end: 14,
                  },
                },
              ],
            },
          ],
        },
      },
    ],
  },
};

export const stubSseEvents: Record<string, SseEvent[]> = {
  "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2": [
    {
      event: "state",
      payload: {
        run_id: "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2",
        state: "accepted",
      },
    },
    {
      event: "message",
      payload: {
        run_id: "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2",
        text: "ユーザ指示を受け付けました。",
      },
    },
    {
      event: "state",
      payload: {
        run_id: "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2",
        state: "running",
      },
    },
    {
      event: "message",
      payload: {
        run_id: "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2",
        text: "入力内容に関連する資料を確認しています。",
      },
    },
    {
      event: "message",
      payload: {
        run_id: "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2",
        text: "参照元候補と回答内容の対応を検証しています。",
      },
    },
    {
      event: "answer",
      payload: {
        run_id: "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2",
        state: "completed",
        answer: {
          blocks: [
            {
              markdown: `入力内容に対する整理結果です。

- 目的、利用者、制約を先にそろえると、後続の設計判断がぶれにくくなります。
- 参照元を回答に紐づけておくと、履歴再表示時にも根拠を確認できます。
- 回答内の図や画像はCodex成果物として保存し、本文から配信用URLで参照します。

## 処理の流れ

\`\`\`mermaid
flowchart TD
  A[ユーザ指示を受け付ける] --> B[関連資料を確認する]
  B --> C[回答案を作成する]
  C --> D[参照元との対応を検証する]
  D --> E[回答と参照元リンクを表示する]
\`\`\`

## 確認観点

| 観点 | 内容 | 確認結果 |
| --- | --- | --- |
| 目的 | 何を達成したいかを先にそろえる。 | 整理済み |
| 根拠 | 回答と参照元の対応を確認できる。 | 整理済み |
| 再表示 | 履歴から同じ内容を確認できる。 | 整理済み |

## 出力例

\`\`\`json
{
  "summary": "目的、根拠、再表示性を確認しました。",
  "references": [
    {
      "source_type": "pdf",
      "label": "SEC BOOKS 開発指針手引き",
      "locator": {
        "page_start": 10,
        "page_end": 14
      }
    }
  ]
}
\`\`\`

![資料検索と参照元確認の分析イメージ](/api/artifacts/6a9158c3-ae1c-4a13-9494-940df193ceef)`,
              references: [
                {
                  source_type: "pdf",
                  label: "SEC BOOKS 開発指針手引き",
                  url: "/api/references/9052af11-89cc-4273-bd2d-ad310805c442",
                  locator: {
                    page_start: 10,
                    page_end: 14,
                  },
                },
              ],
            },
          ],
        },
      },
    },
  ],
};

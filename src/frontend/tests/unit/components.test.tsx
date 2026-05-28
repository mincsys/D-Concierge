import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ActionMenuPopover } from "@/components/action-menu/ActionMenuPopover";
import { AppShell } from "@/components/layout/AppShell";
import { TopMenu } from "@/components/layout/TopMenu";
import { Providers } from "@/app/providers";
import { AnswerContent } from "@/features/answer-rendering/components/AnswerContent";
import { ImageViewerDialog } from "@/features/answer-rendering/components/ImageViewerDialog";
import { MarkdownRenderer } from "@/features/answer-rendering/components/MarkdownRenderer";
import { MermaidRenderer } from "@/features/answer-rendering/components/MermaidRenderer";
import { MermaidViewerDialog } from "@/features/answer-rendering/components/MermaidViewerDialog";
import { ChatComposer } from "@/features/chat/components/ChatComposer";
import { ChatHistoryList } from "@/features/chat/components/ChatHistoryList";
import { ChatStartScreen } from "@/features/chat/components/ChatStartScreen";
import { ChatThread } from "@/features/chat/components/ChatThread";
import { ThoughtPanel } from "@/features/chat/components/ThoughtPanel";
import { splitRevealChunks, revealSubmittedAnswer } from "@/features/chat/lib/revealAnswer";
import type { ChatAnswer, ChatHistoryItem, ChatSession } from "@/features/chat/model/types";
import { ReferenceLink } from "@/features/reference-viewer/components/ReferenceLink";
import { ReferenceViewerDialog } from "@/features/reference-viewer/components/ReferenceViewerDialog";
import { formatPdfPageRange } from "@/features/reference-viewer/lib/pageRange";
import { PdfPageViewer } from "@/features/reference-viewer/viewers/PdfPageViewer";
import { cn } from "@/lib/utils";

const mermaidMocks = vi.hoisted(() => ({
  initialize: vi.fn(),
  render: vi.fn<(id: string, source: string) => Promise<{ svg: string }>>(),
}));

const zoomMocks = vi.hoisted(() => ({
  setTransform: vi.fn(),
  zoomIn: vi.fn(),
  zoomOut: vi.fn(),
}));

const pdfMocks = vi.hoisted(() => ({
  getDocument: vi.fn<(url: string) => { promise: Promise<TestPdfDocument> }>(),
}));

vi.mock("mermaid", () => ({
  default: {
    initialize: mermaidMocks.initialize,
    render: mermaidMocks.render,
  },
}));

vi.mock("react-zoom-pan-pinch", () => ({
  TransformComponent: ({ children }: { children: ReactNode }) => (
    <div data-testid="transform-component">{children}</div>
  ),
  TransformWrapper: ({ children }: { children: ReactNode }) => (
    <div data-testid="transform-wrapper">{children}</div>
  ),
  useControls: () => zoomMocks,
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: pdfMocks.getDocument,
}));

describe("frontend components", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(() => Promise.resolve()) },
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
      () => ({ setTransform: vi.fn() }) as unknown as CanvasRenderingContext2D,
    );
    mermaidMocks.render.mockResolvedValue({
      svg: '<svg viewBox="0 0 200 100"><text>図</text></svg>',
    });
    pdfMocks.getDocument.mockReturnValue({ promise: Promise.resolve(createPdfDocument(3)) });
  });

  afterEach(() => {
    vi.useRealTimers();
    mermaidMocks.initialize.mockClear();
    mermaidMocks.render.mockReset();
    zoomMocks.setTransform.mockClear();
    zoomMocks.zoomIn.mockClear();
    zoomMocks.zoomOut.mockClear();
    pdfMocks.getDocument.mockReset();
  });

  it("観点：ChatComposer。確認：送信、空白抑止、Ctrl+Enter、キャンセル表示を処理する。", async () => {
    const user = userEvent.setup();
    const submitted: string[] = [];
    const canceled = vi.fn();
    const { rerender } = render(
      <Providers>
        <ChatComposer onCancel={canceled} onSubmit={(message) => submitted.push(message)} />
      </Providers>,
    );

    expect(screen.getByLabelText("送信")).toBeDisabled();
    expect(screen.getByLabelText("送信")).toHaveClass("disabled:bg-[var(--dc-muted)]");
    expect(screen.getByLabelText("送信")).not.toHaveClass("bg-linear-to-b");
    await user.type(screen.getByPlaceholderText("指示を入力してください"), "   ");
    await user.click(screen.getByLabelText("送信"));
    expect(screen.getByText("ユーザ指示を入力してください。")).toBeInTheDocument();
    expect(submitted).toEqual([]);

    await user.clear(screen.getByPlaceholderText("指示を入力してください"));
    await user.type(screen.getByPlaceholderText("指示を入力してください"), "  要約  ");
    await user.click(screen.getByLabelText("送信"));
    expect(submitted).toEqual(["要約"]);
    expect(screen.getByPlaceholderText("指示を入力してください")).toHaveValue("");

    await user.type(screen.getByPlaceholderText("指示を入力してください"), "続き");
    fireEvent.keyDown(screen.getByPlaceholderText("指示を入力してください"), {
      ctrlKey: true,
      key: "Enter",
    });
    expect(submitted).toEqual(["要約", "続き"]);

    rerender(
      <Providers>
        <ChatComposer actionMode="cancel" onCancel={canceled} onSubmit={vi.fn()} />
      </Providers>,
    );
    await user.click(screen.getByLabelText("キャンセル"));
    expect(canceled).toHaveBeenCalledTimes(1);

    rerender(
      <Providers>
        <ChatComposer actionMode="canceling" onCancel={canceled} onSubmit={vi.fn()} />
      </Providers>,
    );
    expect(screen.getByLabelText("キャンセル処理中")).toBeDisabled();
  });

  it("観点：ChatStartScreen。確認：候補クリックで入力し、送信イベントを発行する。", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    render(
      <Providers>
        <ChatStartScreen
          inputSuggestions={["資料を要約", "差分を整理"]}
          welcomeMessage="ようこそ"
          onStart={onStart}
        />
      </Providers>,
    );

    expect(screen.getByRole("heading", { name: "ようこそ" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "差分を整理" }));
    expect(screen.getByPlaceholderText("指示を入力してください")).toHaveValue("差分を整理");
    await user.click(screen.getByLabelText("送信"));
    expect(onStart).toHaveBeenCalledWith("差分を整理");
  });

  it("観点：ChatStartScreen。確認：歓迎メッセージと入力候補の改行を表示し、候補クリックで改行を維持する。", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <ChatStartScreen
          inputSuggestions={["候補1行目\n候補2行目"]}
          welcomeMessage={"1行目\n2行目"}
          onStart={vi.fn()}
        />
      </Providers>,
    );

    const heading = screen.getByRole("heading", { name: /1行目\s+2行目/ });
    const suggestion = screen.getByRole("button", { name: /候補1行目\s+候補2行目/ });

    expect(heading).toHaveClass("whitespace-pre-line");
    expect(suggestion).toHaveClass("whitespace-pre-line", "min-h-[54px]");
    await user.click(suggestion);
    expect(screen.getByPlaceholderText("指示を入力してください")).toHaveValue(
      "候補1行目\n候補2行目",
    );
  });

  it("観点：ChatHistoryList。確認：長い履歴名は領域内で省略表示できる。", async () => {
    const user = userEvent.setup();
    const onOpenAnswer = vi.fn();
    const longTitle =
      "C++の組み込みソフトのコーディングで移植性を重視した書き方をするにはどうすればいいですか？";

    render(
      <Providers>
        <ChatHistoryList
          activeChatId="chat-1"
          histories={[{ chatId: "chat-1", title: longTitle } as ChatHistoryItem]}
          onOpenAnswer={onOpenAnswer}
        />
      </Providers>,
    );

    const historyButton = screen.getByRole("button", { name: longTitle });
    const title = screen.getByText(longTitle);
    expect(historyButton).toHaveAttribute("title", longTitle);
    expect(historyButton).toHaveClass("min-w-0", "overflow-hidden", "pr-8", "group-hover:pr-12");
    expect(title).toHaveClass("block", "min-w-0", "truncate");
    await user.click(historyButton);
    expect(onOpenAnswer).toHaveBeenCalledWith("chat-1");
  });

  it("観点：ChatHistoryList。確認：履歴項目ホバー用メニューから削除項目を表示し、履歴選択を抑止する。", async () => {
    const user = userEvent.setup();
    const onOpenAnswer = vi.fn();
    const onRequestDelete = vi.fn();
    const histories = [history("chat-1", "Codex 実行時フォーマット検査")];

    render(
      <Providers>
        <ChatHistoryList
          activeChatId="chat-1"
          histories={histories}
          onOpenAnswer={onOpenAnswer}
          onRequestDelete={onRequestDelete}
        />
      </Providers>,
    );

    const menuButton = screen.getByRole("button", {
      name: "Codex 実行時フォーマット検査のメニュー",
    });
    expect(menuButton).toHaveClass("opacity-0", "group-hover:opacity-100");

    await user.hover(screen.getByRole("button", { name: "Codex 実行時フォーマット検査" }));
    await user.click(menuButton);
    expect(onOpenAnswer).not.toHaveBeenCalled();
    expect(screen.getByRole("menu", { name: "履歴項目メニュー" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "削除する" })).toHaveClass(
      "text-[var(--dc-danger)]",
    );
    await user.click(screen.getByRole("menuitem", { name: "削除する" }));
    expect(onRequestDelete).toHaveBeenCalledWith("chat-1");
  });

  it("観点：ActionMenuPopover。確認：通常項目は黒系、削除項目だけ赤系で表示する。", () => {
    render(
      <Providers>
        <ActionMenuPopover
          open
          ariaLabel="操作メニュー"
          items={[
            { icon: <span aria-hidden="true" />, label: "通常項目" },
            { icon: <span aria-hidden="true" />, label: "削除する", tone: "danger" },
          ]}
          onOpenChange={vi.fn()}
        />
      </Providers>,
    );

    expect(screen.getByRole("menuitem", { name: "通常項目" })).toHaveClass("text-[var(--dc-text)]");
    expect(screen.getByRole("menuitem", { name: "削除する" })).toHaveClass(
      "text-[var(--dc-danger)]",
    );
  });

  it("観点：AppShellとSidebar。確認：履歴、新規開始、折りたたみ表示を切り替える。", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const onOpen = vi.fn();
    const histories = [history("chat-1", "履歴1"), history("chat-2", "履歴2")];
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1280,
      writable: true,
    });

    render(
      <Providers>
        <AppShell
          activeChatId="chat-2"
          currentUser={{ userId: "demo-user", userName: "デモユーザ" }}
          histories={histories}
          onOpenAnswer={onOpen}
          onStartNewChat={onStart}
        >
          {({ sidebarCollapsed }) => <div>{sidebarCollapsed ? "狭い" : "広い"}</div>}
        </AppShell>
      </Providers>,
    );

    expect(document.querySelector('[data-slot="scroll-area-viewport"]')).toHaveClass(
      "[&>div]:!block",
      "[&>div]:!min-w-0",
      "[&>div]:!w-full",
    );
    await user.click(screen.getByRole("button", { name: "履歴1" }));
    expect(onOpen).toHaveBeenCalledWith("chat-1");
    const newChatButton = screen.getByRole("button", { name: /新しいチャット/ });
    expect(newChatButton).toHaveClass("shadow-xs");
    expect(newChatButton).not.toHaveClass("shadow-[0_10px_18px_var(--dc-shadow-primary)]");
    await user.click(newChatButton);
    expect(onStart).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "サイドバー切替" }));
    expect(screen.getByLabelText("折りたたみサイドバー")).toBeInTheDocument();
    const collapsedNewChatButton = screen.getByRole("button", { name: "新しいチャット" });
    expect(collapsedNewChatButton).toHaveClass("shadow-xs");
    expect(collapsedNewChatButton).not.toHaveClass("shadow-[0_10px_18px_var(--dc-shadow-primary)]");
    expect(screen.getByText("狭い")).toBeInTheDocument();
  });

  it("観点：AppShell。確認：開始画面では右上のその他メニューを表示しない。", () => {
    render(
      <Providers>
        <AppShell
          currentUser={{ userId: "demo-user", userName: "デモユーザ" }}
          histories={[]}
          onOpenAnswer={vi.fn()}
          onStartNewChat={vi.fn()}
        >
          <div>開始画面</div>
        </AppShell>
      </Providers>,
    );

    expect(screen.getByText("開始画面")).toBeInTheDocument();
    expect(screen.queryByLabelText("その他")).not.toBeInTheDocument();
  });

  it("観点：AppShell自動折りたたみ。確認：狭い幅で折りたたみ、広い幅で復帰し、通常childrenも表示する。", async () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 900,
      writable: true,
    });

    render(
      <Providers>
        <AppShell
          currentUser={{ userId: "demo-user", userName: "デモユーザ" }}
          histories={[]}
          onOpenAnswer={vi.fn()}
          onStartNewChat={vi.fn()}
        >
          <div>固定children</div>
        </AppShell>
      </Providers>,
    );

    await waitFor(() => expect(screen.getByLabelText("折りたたみサイドバー")).toBeInTheDocument());
    expect(screen.getByText("固定children")).toBeInTheDocument();

    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1280,
      writable: true,
    });
    await act(async () => window.dispatchEvent(new Event("resize")));
    expect(screen.getByText("D-Concierge")).toBeInTheDocument();
  });

  it("観点：TopMenu。確認：その他メニューから削除項目を表示する。", async () => {
    const user = userEvent.setup();
    const onRequestDelete = vi.fn();
    render(
      <Providers>
        <TopMenu onRequestDelete={onRequestDelete} />
      </Providers>,
    );

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await user.click(screen.getByLabelText("その他"));
    expect(screen.getByRole("menu", { name: "その他メニュー" })).toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "削除する" }));
    expect(onRequestDelete).toHaveBeenCalledTimes(1);
  });

  it("観点：ChatThread。確認：中間、回答、状態メッセージ、キャンセル、継続指示を表示・通知する。", async () => {
    const user = userEvent.setup();
    const onToggleThought = vi.fn();
    const onOpenPdf = vi.fn();
    const onCancelRun = vi.fn();
    const onSubmitInstruction = vi.fn();
    const { container, rerender } = render(
      <Providers>
        <ChatThread
          cancelingRunId={null}
          openThoughtRunIds={new Set(["run-1"])}
          scrollReserveRunId="run-2"
          scrollTargetRunId="run-2"
          session={chatSession()}
          sidebarCollapsed={false}
          onCancelRun={onCancelRun}
          onOpenPdf={onOpenPdf}
          onScrollTargetHandled={vi.fn()}
          onSubmitInstruction={onSubmitInstruction}
          onToggleThought={onToggleThought}
        />
      </Providers>,
    );

    expect(screen.getByText("初回指示")).toBeInTheDocument();
    expect(screen.getByText("調査中")).toBeInTheDocument();
    expect(screen.getByText("回答本文")).toBeInTheDocument();
    expect(screen.getByText("回答生成に失敗しました。")).toHaveClass("whitespace-pre-line");
    expect(container.querySelectorAll(".animate-spin")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: /資料 p.1-2/ }));
    expect(onOpenPdf).toHaveBeenCalledWith(reference());
    expect(screen.getAllByRole("button", { name: /作業プロセス/ })).toHaveLength(3);
    await user.click(screen.getAllByRole("button", { name: /作業プロセス/ })[0]);
    expect(onToggleThought).toHaveBeenCalledWith("run-1");
    await user.click(screen.getByLabelText("キャンセル"));
    expect(onCancelRun).toHaveBeenCalledWith("run-3");

    rerender(
      <Providers>
        <ChatThread
          cancelingRunId={null}
          openThoughtRunIds={new Set(["run-1"])}
          session={completedChatSession()}
          sidebarCollapsed={false}
          onCancelRun={onCancelRun}
          onOpenPdf={onOpenPdf}
          onScrollTargetHandled={vi.fn()}
          onSubmitInstruction={onSubmitInstruction}
          onToggleThought={onToggleThought}
        />
      </Providers>,
    );
    expect(container.querySelectorAll(".animate-spin")).toHaveLength(0);
    await user.type(screen.getByPlaceholderText("指示を入力してください"), "追加");
    fireEvent.keyDown(screen.getByPlaceholderText("指示を入力してください"), {
      metaKey: true,
      key: "Enter",
    });
    expect(onSubmitInstruction).toHaveBeenCalledWith("追加");
  });

  it("観点：Answer/Markdown表示。確認：参照元、コード、Mermaid、許可画像、危険HTMLを処理する。", async () => {
    const user = userEvent.setup();
    const onOpenPdf = vi.fn();
    render(
      <Providers>
        <AnswerContent
          answer={{
            blocks: [
              {
                markdown:
                  "本文\n\n`inline`\n\n```ts\nconst a = 1;\n```\n\n```mermaid\ngraph TD;A-->B;\n```\n\n![ok](/api/artifacts/a.png)\n![ng](https://evil.example/a.png)\n<script>alert(1)</script>",
                references: [reference()],
              },
            ],
          }}
          onOpenPdf={onOpenPdf}
        />
      </Providers>,
    );

    expect(screen.getByText("本文")).toBeInTheDocument();
    expect(screen.getByText("inline")).toBeInTheDocument();
    expect(screen.getByText("const a = 1;")).toBeInTheDocument();
    expect(screen.getByAltText("ok")).toHaveAttribute("src", "/api/artifacts/a.png");
    fireEvent.error(screen.getByAltText("ok"));
    expect(screen.getByText("一部のCodex成果物を表示できませんでした。")).toBeInTheDocument();
    expect(screen.queryByAltText("ng")).not.toBeInTheDocument();
    expect(screen.queryByText("alert(1)")).not.toBeInTheDocument();
    await user.click(screen.getByLabelText("コードをコピー"));
    await waitFor(() => expect(screen.getByLabelText("コピーしました")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /資料 p.1-2/ }));
    expect(onOpenPdf).toHaveBeenCalledWith(reference());
    await waitFor(() => expect(mermaidMocks.render).toHaveBeenCalled());
  });

  it("観点：AnswerContent。確認：参照元が空の場合は参照元領域を表示しない。", () => {
    render(
      <Providers>
        <AnswerContent
          answer={{ blocks: [{ markdown: "参照なし回答", references: [] }] }}
          onOpenPdf={vi.fn()}
        />
      </Providers>,
    );

    expect(screen.getByText("参照なし回答")).toBeInTheDocument();
    expect(screen.queryByLabelText("参照元")).not.toBeInTheDocument();
  });

  it("観点：Markdownリンクとコピー失敗。確認：hrefなしリンクとクリップボード失敗を安全に扱う。", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(() => Promise.reject(new Error("denied"))) },
    });
    render(
      <Providers>
        <MarkdownRenderer markdown={"[リンク](https://example.com)\n\n```\ncode\n```"} />
      </Providers>,
    );

    expect(screen.getByRole("link", { name: "リンク" })).toHaveAttribute(
      "href",
      "https://example.com",
    );
    await user.click(screen.getByLabelText("コードをコピー"));
    expect(screen.getByLabelText("コードをコピー")).toBeInTheDocument();
  });

  it("観点：Markdown HTML変換。確認：hrefなしリンクとaltなし許可画像を安全に表示する。", () => {
    const { container } = render(
      <Providers>
        <MarkdownRenderer
          markdown={
            '<a>hrefなし</a>\n\n<img src="/api/artifacts/no-alt.png">\n\n<pre><code class="language-ts"><span>span</span>tail</code></pre>\n\n<pre><code class="language-ts"><span>only element</span></code></pre>'
          }
        />
      </Providers>,
    );

    expect(screen.getByText("hrefなし")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "hrefなし" })).not.toBeInTheDocument();
    expect(container.querySelector("img.markdown-image")).toHaveAttribute(
      "src",
      "/api/artifacts/no-alt.png",
    );
    expect(screen.getAllByText("ts")).toHaveLength(2);
  });

  it("観点：Markdown画像拡大表示。確認：許可画像はビューアで拡大表示でき、外部画像は出力しない。", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <MarkdownRenderer
          markdown={"![成果物画像](/api/artifacts/a.png)\n\n![外部](https://evil.example/a.png)"}
        />
      </Providers>,
    );

    expect(screen.getByAltText("成果物画像")).toHaveAttribute("src", "/api/artifacts/a.png");
    expect(screen.queryByAltText("外部")).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("画像を拡大表示"));
    expect(screen.getByRole("dialog", { name: "画像" })).toBeInTheDocument();
    expect(screen.getAllByAltText("成果物画像")).toHaveLength(2);
  });

  it("観点：MermaidRenderer。確認：描画成功、拡大、描画失敗を表示する。", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <Providers>
        <MermaidRenderer source="graph TD;A-->B;" />
      </Providers>,
    );

    await waitFor(() => expect(screen.getByText("図")).toBeInTheDocument());
    await user.click(screen.getByLabelText("Mermaid図を拡大表示"));
    expect(screen.getByRole("dialog", { name: "Mermaid図" })).toBeInTheDocument();

    mermaidMocks.render.mockRejectedValueOnce(new Error("parse error"));
    rerender(
      <Providers>
        <MermaidRenderer source="broken" />
      </Providers>,
    );
    await waitFor(() =>
      expect(screen.getByText("Mermaid図を表示できませんでした。")).toBeInTheDocument(),
    );
  });

  it("観点：MermaidRenderer。確認：再描画時に描画IDを使い回さない。", async () => {
    const { rerender } = render(
      <Providers>
        <MermaidRenderer source="graph TD;A-->B;" />
      </Providers>,
    );
    await waitFor(() => expect(mermaidMocks.render).toHaveBeenCalledTimes(1));

    rerender(
      <Providers>
        <MermaidRenderer source="graph TD;A-->C;" />
      </Providers>,
    );
    await waitFor(() => expect(mermaidMocks.render).toHaveBeenCalledTimes(2));

    const firstId = mermaidMocks.render.mock.calls[0]?.[0];
    const secondId = mermaidMocks.render.mock.calls[1]?.[0];
    expect(firstId).toBeTruthy();
    expect(secondId).toBeTruthy();
    expect(firstId).not.toBe(secondId);
  });

  it("観点：MermaidRenderer。確認：StrictMode配下でも正常な図を失敗表示にしない。", async () => {
    render(
      <StrictMode>
        <Providers>
          <MermaidRenderer source="graph TD;A-->B;" />
        </Providers>
      </StrictMode>,
    );

    await waitFor(() => expect(screen.getByText("図")).toBeInTheDocument());
    expect(screen.queryByText("Mermaid図を表示できませんでした。")).not.toBeInTheDocument();
  });

  it("観点：MermaidRenderer。確認：描画失敗時にMermaidの一時エラーDOMを残さない。", async () => {
    mermaidMocks.render.mockImplementationOnce((id: string) => {
      const injectedError = document.createElement("div");
      injectedError.id = id;
      injectedError.textContent = "Syntax error in text mermaid version 11.14.0";
      document.body.appendChild(injectedError);
      return Promise.reject(new Error("parse error"));
    });

    render(
      <Providers>
        <MermaidRenderer source="broken" />
      </Providers>,
    );

    await waitFor(() =>
      expect(screen.getByText("Mermaid図を表示できませんでした。")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Syntax error in text/)).not.toBeInTheDocument();
  });

  it("観点：MermaidRendererのアンマウント。確認：描画完了前に破棄された場合は状態更新しない。", async () => {
    let resolveRender: (value: { svg: string }) => void = () => undefined;
    let pendingRenderId = "";
    mermaidMocks.render.mockImplementationOnce((id: string) => {
      pendingRenderId = id;
      const injectedElement = document.createElement("div");
      injectedElement.id = id;
      document.body.appendChild(injectedElement);
      return new Promise((resolve) => {
        resolveRender = resolve;
      });
    });
    const { unmount } = render(
      <Providers>
        <MermaidRenderer source="graph TD;A-->B;" />
      </Providers>,
    );

    unmount();
    expect(document.getElementById(pendingRenderId)).toBeInTheDocument();
    await act(async () => resolveRender({ svg: "<svg><text>遅延図</text></svg>" }));
    expect(screen.queryByText("遅延図")).not.toBeInTheDocument();
    expect(document.getElementById(pendingRenderId)).not.toBeInTheDocument();

    let rejectRender: (reason: Error) => void = () => undefined;
    let rejectedRenderId = "";
    mermaidMocks.render.mockImplementationOnce((id: string) => {
      rejectedRenderId = id;
      const injectedElement = document.createElement("div");
      injectedElement.id = id;
      document.body.appendChild(injectedElement);
      return new Promise((_, reject) => {
        rejectRender = reject;
      });
    });
    const rejected = render(
      <Providers>
        <MermaidRenderer source="broken" />
      </Providers>,
    );

    rejected.unmount();
    expect(document.getElementById(rejectedRenderId)).toBeInTheDocument();
    await act(async () => rejectRender(new Error("parse error")));
    expect(screen.queryByText("Mermaid図を表示できませんでした。")).not.toBeInTheDocument();
    expect(document.getElementById(rejectedRenderId)).not.toBeInTheDocument();
  });

  it("観点：MermaidViewerDialog。確認：拡大縮小と全体表示を操作する。", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <MermaidViewerDialog
          open
          svg={'<svg width="200px" height="100px"><text>図</text></svg>'}
          onOpenChange={vi.fn()}
        />
      </Providers>,
    );

    await user.click(screen.getByLabelText("Mermaid図を拡大"));
    await user.click(screen.getByLabelText("Mermaid図を縮小"));
    await user.click(screen.getByLabelText("Mermaid図全体を表示"));
    expect(zoomMocks.zoomIn).toHaveBeenCalledWith(0.1);
    expect(zoomMocks.zoomOut).toHaveBeenCalledWith(0.1);
    await waitFor(() => expect(zoomMocks.setTransform).toHaveBeenCalled());
  });

  it("観点：MermaidViewerDialogの寸法計算。確認：寸法なし、無効寸法、要素矩形からの全体表示を扱う。", async () => {
    const user = userEvent.setup();
    const originalGetBoundingClientRect = SVGElement.prototype.getBoundingClientRect;
    render(
      <Providers>
        <MermaidViewerDialog open svg="<svg></svg>" onOpenChange={vi.fn()} />
      </Providers>,
    );

    await user.click(screen.getByLabelText("Mermaid図全体を表示"));
    expect(zoomMocks.setTransform).not.toHaveBeenCalled();

    cleanup();
    SVGElement.prototype.getBoundingClientRect = () =>
      ({
        bottom: 80,
        height: 80,
        left: 0,
        right: 160,
        top: 0,
        width: 160,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }) as DOMRect;
    render(
      <Providers>
        <MermaidViewerDialog
          open
          svg={'<svg width="invalid" height="100px"></svg>'}
          onOpenChange={vi.fn()}
        />
      </Providers>,
    );

    await user.click(screen.getByLabelText("Mermaid図全体を表示"));
    await waitFor(() => expect(zoomMocks.setTransform).toHaveBeenCalled());
    SVGElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });

  it("観点：ImageViewerDialog。確認：拡大縮小と全体表示を操作する。", async () => {
    const user = userEvent.setup();
    const naturalWidth = Object.getOwnPropertyDescriptor(
      HTMLImageElement.prototype,
      "naturalWidth",
    );
    const naturalHeight = Object.getOwnPropertyDescriptor(
      HTMLImageElement.prototype,
      "naturalHeight",
    );
    Object.defineProperty(HTMLImageElement.prototype, "naturalWidth", {
      configurable: true,
      get: () => 240,
    });
    Object.defineProperty(HTMLImageElement.prototype, "naturalHeight", {
      configurable: true,
      get: () => 120,
    });

    render(
      <Providers>
        <ImageViewerDialog
          alt="成果物画像"
          open
          src="/api/artifacts/a.png"
          onOpenChange={vi.fn()}
        />
      </Providers>,
    );

    fireEvent.load(screen.getByAltText("成果物画像"));
    await user.click(screen.getByLabelText("画像を拡大"));
    await user.click(screen.getByLabelText("画像を縮小"));
    await user.click(screen.getByLabelText("画像全体を表示"));
    expect(zoomMocks.zoomIn).toHaveBeenCalledWith(0.1);
    expect(zoomMocks.zoomOut).toHaveBeenCalledWith(0.1);
    await waitFor(() => expect(zoomMocks.setTransform).toHaveBeenCalled());

    if (naturalWidth) {
      Object.defineProperty(HTMLImageElement.prototype, "naturalWidth", naturalWidth);
    }
    if (naturalHeight) {
      Object.defineProperty(HTMLImageElement.prototype, "naturalHeight", naturalHeight);
    }
  });

  it("観点：参照元表示。確認：ページ範囲、リンク、PDFダイアログなし状態を処理する。", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const longReferenceLabel =
      "SEC BOOKS：ESCR C++ Ver. 2.0：【改訂版】組込みソフトウェア開発向けコーディング作法ガイド［C++言語版］ Ver. 2.0.pdf p.181-192";
    const { rerender } = render(
      <Providers>
        <ReferenceLink label={longReferenceLabel} onClick={onClick} />
        <ReferenceViewerDialog open reference={null} onOpenChange={vi.fn()} />
      </Providers>,
    );

    const referenceLink = screen.getByRole("button", { name: longReferenceLabel });
    expect(referenceLink).toHaveClass(
      "w-full",
      "max-w-full",
      "min-w-0",
      "whitespace-normal",
      "break-words",
      "[overflow-wrap:anywhere]",
    );
    await user.click(referenceLink);
    expect(onClick).toHaveBeenCalled();
    expect(formatPdfPageRange(reference())).toBe("p.1-2");
    expect(formatPdfPageRange({ locator: { page_end: 3, page_start: 3 } })).toBe("p.3");

    rerender(
      <Providers>
        <ReferenceViewerDialog open reference={reference()} onOpenChange={vi.fn()} />
      </Providers>,
    );
    expect(screen.getByRole("dialog", { name: "資料" })).toBeInTheDocument();
    expect(screen.getByText("資料")).toBeInTheDocument();
  });

  it("観点：PdfPageViewer。確認：PDF読込、参照元ページ強調、読込失敗、範囲不正を処理する。", async () => {
    const { rerender } = render(<PdfPageViewer reference={reference()} />);

    await waitFor(() => expect(screen.getByText("参照元ページ p.1")).toBeInTheDocument());
    expect(screen.getByText("参照元ページ p.2")).toBeInTheDocument();
    expect(screen.getByText("p.3")).toBeInTheDocument();
    expect(screen.getAllByTestId("pdf-canvas")).toHaveLength(3);

    pdfMocks.getDocument.mockReturnValueOnce({
      promise: Promise.reject(new Error("PDFを取得できません。")),
    });
    rerender(<PdfPageViewer reference={{ ...reference(), url: "/api/references/error" }} />);
    await waitFor(() =>
      expect(screen.getByText("参照元を表示できませんでした。")).toBeInTheDocument(),
    );

    pdfMocks.getDocument.mockReturnValueOnce({ promise: Promise.resolve(createPdfDocument(2)) });
    rerender(
      <PdfPageViewer
        reference={{
          ...reference(),
          locator: { page_end: 5, page_start: 4 },
          url: "/api/references/out-of-range",
        }}
      />,
    );
    await waitFor(() => expect(screen.getByText("p.1")).toBeInTheDocument());
    expect(screen.getByText("参照元の位置情報を表示できませんでした。")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByTestId("pdf-canvas")).toHaveLength(2));
  });

  it("観点：PdfPageViewerの破棄と異常系。確認：読込中破棄、非Error失敗、Canvas contextなしを扱う。", async () => {
    let resolvePdf: (document: TestPdfDocument) => void = () => undefined;
    const pendingDocument = new Promise<TestPdfDocument>((resolve) => {
      resolvePdf = resolve;
    });
    pdfMocks.getDocument.mockReturnValueOnce({ promise: pendingDocument });
    const { unmount } = render(<PdfPageViewer reference={reference()} />);

    unmount();
    await act(async () => resolvePdf(createPdfDocument(1)));
    expect(screen.queryByText("p.1")).not.toBeInTheDocument();

    pdfMocks.getDocument.mockReturnValueOnce({ promise: Promise.reject("broken") });
    render(<PdfPageViewer reference={{ ...reference(), url: "/api/references/string-error" }} />);
    await waitFor(() =>
      expect(screen.getByText("参照元を表示できませんでした。")).toBeInTheDocument(),
    );
  });

  it("観点：回答表示演出。確認：Mermaidブロックを保持して分割し、旧ストリーム化時は中断する。", async () => {
    vi.useFakeTimers();
    const answer: ChatAnswer = {
      blocks: [
        {
          markdown: "123456789```mermaid\ngraph TD;A-->B;\n```abcdefghi",
          references: [],
        },
      ],
    };
    expect(splitRevealChunks(answer.blocks[0].markdown)).toEqual([
      "12345678",
      "9",
      "```mermaid\ngraph TD;A-->B;\n```",
      "abcdefgh",
      "i",
    ]);

    const events: string[] = [];
    const first = revealSubmittedAnswer({
      answer,
      isCurrent: () => true,
      onAnswerComplete: () => events.push("complete"),
      onAnswerChange: (_runId, changedAnswer) => events.push(changedAnswer.blocks[0].markdown),
      onAnswerStart: () => events.push("start"),
      onThoughtComplete: () => events.push("thought"),
      runId: "run-1",
    });
    await vi.runAllTimersAsync();
    await first;
    expect(events.at(0)).toBe("thought");
    expect(events).toContain("complete");

    const interrupted = revealSubmittedAnswer({
      answer,
      isCurrent: () => false,
      onAnswerComplete: () => events.push("interrupted-complete"),
      onAnswerChange: () => events.push("interrupted-markdown"),
      onAnswerStart: () => events.push("interrupted-start"),
      onThoughtComplete: () => events.push("interrupted-thought"),
      runId: "run-2",
    });
    await vi.runAllTimersAsync();
    await interrupted;
    expect(events).not.toContain("interrupted-start");
  });

  it("観点：回答表示演出の中断。確認：回答開始後、チャンク途中、空本文をそれぞれ扱う。", async () => {
    vi.useFakeTimers();
    const events: string[] = [];
    let current = true;
    const reveal = revealSubmittedAnswer({
      answer: { blocks: [{ markdown: "123456789abcdef", references: [] }] },
      isCurrent: () => current,
      onAnswerComplete: () => events.push("complete"),
      onAnswerChange: (_runId, answer) => {
        events.push(answer.blocks[0].markdown);
        current = false;
      },
      onAnswerStart: () => events.push("start"),
      onThoughtComplete: () => events.push("thought"),
      runId: "run-1",
    });

    await vi.runAllTimersAsync();
    await reveal;
    expect(events).toEqual(["thought", "start", "12345678"]);

    const emptyEvents: string[] = [];
    const empty = revealSubmittedAnswer({
      answer: { blocks: [{ markdown: "", references: [] }] },
      isCurrent: () => true,
      onAnswerComplete: () => emptyEvents.push("complete"),
      onAnswerChange: () => emptyEvents.push("markdown"),
      onAnswerStart: () => emptyEvents.push("start"),
      onThoughtComplete: () => emptyEvents.push("thought"),
      runId: "run-2",
    });
    await vi.runAllTimersAsync();
    await empty;
    expect(emptyEvents).toEqual(["thought", "start", "markdown", "complete"]);
    expect(splitRevealChunks("```mermaid\ngraph TD;A-->B;\n```")).toEqual([
      "```mermaid\ngraph TD;A-->B;\n```",
    ]);
    expect(splitRevealChunks("")).toEqual([]);
  });

  it("観点：回答表示演出の最新性確認。確認：チャンク境界で旧ストリーム化した場合に中断する。", async () => {
    vi.useFakeTimers();
    let checks = 0;
    const events: string[] = [];
    const reveal = revealSubmittedAnswer({
      answer: { blocks: [{ markdown: "123456789abcdef", references: [] }] },
      isCurrent: () => {
        checks += 1;
        return checks < 3;
      },
      onAnswerComplete: () => events.push("complete"),
      onAnswerChange: (_runId, answer) => events.push(answer.blocks[0].markdown),
      onAnswerStart: () => events.push("start"),
      onThoughtComplete: () => events.push("thought"),
      runId: "run-3",
    });

    await vi.runAllTimersAsync();
    await reveal;
    expect(events).toEqual(["thought", "start", "12345678"]);
  });

  it("観点：回答表示演出の実タイマー。確認：実タイマーでもチャンク境界の旧ストリーム化で中断する。", async () => {
    vi.useRealTimers();
    let checks = 0;
    const events: string[] = [];

    await revealSubmittedAnswer({
      answer: { blocks: [{ markdown: "123456789abcdef", references: [] }] },
      isCurrent: () => {
        checks += 1;
        return checks < 3;
      },
      onAnswerComplete: () => events.push("complete"),
      onAnswerChange: (_runId, answer) => events.push(answer.blocks[0].markdown),
      onAnswerStart: () => events.push("start"),
      onThoughtComplete: () => events.push("thought"),
      runId: "run-4",
    });

    expect(events).toEqual(["thought", "start", "12345678"]);
  });

  it("観点：ChatStartScreenとThoughtPanelの空状態。確認：歓迎文、候補、思考本文を条件表示する。", () => {
    render(
      <Providers>
        <ChatStartScreen inputSuggestions={[]} onStart={vi.fn()} />
        <ThoughtPanel
          open={false}
          messages={[{ id: "msg-1", text: "閉じた思考" }]}
          onToggle={vi.fn()}
        />
      </Providers>,
    );

    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    expect(screen.queryByText("閉じた思考")).not.toBeInTheDocument();
  });

  it("観点：ChatThread。確認：中間メッセージがないrunでも作業プロセス見出しを表示する。", () => {
    render(
      <Providers>
        <ChatThread
          cancelingRunId={null}
          openThoughtRunIds={new Set(["run-empty"])}
          session={{
            id: "chat-empty",
            runs: [
              {
                intermediateMessages: [],
                runId: "run-empty",
                state: "completed",
                userInstruction: "中間なし",
              },
            ],
            title: "中間なし",
          }}
          sidebarCollapsed={false}
          onCancelRun={vi.fn()}
          onOpenPdf={vi.fn()}
          onScrollTargetHandled={vi.fn()}
          onSubmitInstruction={vi.fn()}
          onToggleThought={vi.fn()}
        />
      </Providers>,
    );

    expect(screen.getByRole("button", { name: /作業プロセス/ })).toBeInTheDocument();
  });

  it("観点：ChatComposerとChatThreadの境界状態。確認：空送信、長文高さ、空セッション、キャンセル中表示を扱う。", async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLTextAreaElement.prototype, "scrollHeight", {
      configurable: true,
      value: 600,
    });
    const submitted = vi.fn();
    const { container, rerender } = render(
      <Providers>
        <ChatComposer onSubmit={submitted} />
      </Providers>,
    );

    const textarea = screen.getByPlaceholderText("指示を入力してください");
    fireEvent.keyDown(textarea, { ctrlKey: true, key: "Enter" });
    expect(submitted).not.toHaveBeenCalled();
    await user.type(textarea, "長文");
    expect(textarea).toHaveStyle({ overflowY: "auto" });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    expect(submitted).toHaveBeenCalledWith("長文");

    const canceled = vi.fn();
    rerender(
      <Providers>
        <ChatComposer actionMode="cancel" onCancel={canceled} onSubmit={submitted} />
      </Providers>,
    );
    fireEvent.keyDown(screen.getByPlaceholderText("指示を入力してください"), {
      ctrlKey: true,
      key: "Enter",
    });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    expect(canceled).toHaveBeenCalledTimes(1);

    const handledMissingScroll = vi.fn();
    rerender(
      <Providers>
        <ChatThread
          cancelingRunId={null}
          openThoughtRunIds={new Set()}
          scrollTargetRunId="missing-run"
          session={{ id: "empty", runs: [], title: "空" }}
          sidebarCollapsed
          onCancelRun={vi.fn()}
          onOpenPdf={vi.fn()}
          onScrollTargetHandled={handledMissingScroll}
          onSubmitInstruction={vi.fn()}
          onToggleThought={vi.fn()}
        />
      </Providers>,
    );
    expect(screen.getByLabelText("送信")).toBeDisabled();
    await waitFor(() => expect(handledMissingScroll).not.toHaveBeenCalled());

    rerender(
      <Providers>
        <ChatThread
          cancelingRunId="run-1"
          openThoughtRunIds={new Set()}
          session={{
            id: "chat-1",
            runs: [
              {
                intermediateMessages: [],
                runId: "run-1",
                state: "running",
                statusMessage: "キャンセル待機中",
                userInstruction: "実行中",
              },
            ],
            title: "キャンセル",
          }}
          sidebarCollapsed
          onCancelRun={vi.fn()}
          onOpenPdf={vi.fn()}
          onScrollTargetHandled={vi.fn()}
          onSubmitInstruction={vi.fn()}
          onToggleThought={vi.fn()}
        />
      </Providers>,
    );
    expect(screen.getByLabelText("キャンセル処理中")).toBeDisabled();

    rerender(
      <Providers>
        <ChatThread
          cancelingRunId={null}
          openThoughtRunIds={new Set()}
          session={{
            id: "chat-1",
            runs: [
              {
                intermediateMessages: [],
                runId: "run-1",
                state: "canceled",
                statusMessage: "キャンセルしました。",
                userInstruction: "キャンセル対象",
              },
            ],
            title: "キャンセル済み",
          }}
          sidebarCollapsed={false}
          onCancelRun={vi.fn()}
          onOpenPdf={vi.fn()}
          onScrollTargetHandled={vi.fn()}
          onSubmitInstruction={vi.fn()}
          onToggleThought={vi.fn()}
        />
      </Providers>,
    );
    expect(screen.getByText("キャンセルしました。")).toHaveClass(
      "rounded-lg",
      "border",
      "text-[var(--dc-muted-strong)]",
    );

    rerender(
      <Providers>
        <ChatThread
          cancelingRunId={null}
          openThoughtRunIds={new Set()}
          session={{
            id: "chat-1",
            runs: [
              {
                intermediateMessages: [],
                runId: "run-1",
                state: "cancel_requested",
                statusMessage: "キャンセルしています。",
                userInstruction: "キャンセル対象",
              },
            ],
            title: "キャンセル要求中",
          }}
          sidebarCollapsed={false}
          onCancelRun={vi.fn()}
          onOpenPdf={vi.fn()}
          onScrollTargetHandled={vi.fn()}
          onSubmitInstruction={vi.fn()}
          onToggleThought={vi.fn()}
        />
      </Providers>,
    );
    expect(screen.getByText("キャンセルしています。")).toHaveClass(
      "rounded-lg",
      "border",
      "text-[var(--dc-muted-strong)]",
    );
  });

  it("観点：ユーティリティ。確認：classNameを結合しTailwind競合を解決する。", () => {
    const hiddenClass = "";

    expect(cn("px-2", hiddenClass, "px-4")).toBe("px-4");
  });
});

function history(chatId: string, title: string): ChatHistoryItem {
  return {
    chatId,
    latestRunId: `${chatId}-run`,
    latestState: "completed",
    title,
    updatedAt: "2026-05-09T10:00:00+09:00",
  };
}

function reference() {
  return {
    label: "資料",
    locator: { page_end: 2, page_start: 1 },
    source_type: "pdf" as const,
    url: "/api/references/ref-1",
  };
}

function chatSession(): ChatSession {
  return {
    id: "chat-1",
    runs: [
      {
        answer: { blocks: [{ markdown: "回答本文", references: [reference()] }] },
        intermediateMessages: [{ id: "msg-1", text: "調査中" }],
        runId: "run-1",
        state: "completed",
        userInstruction: "初回指示",
      },
      {
        intermediateMessages: [],
        runId: "run-2",
        state: "error",
        statusMessage: "回答生成に失敗しました。",
        userInstruction: "追加指示",
      },
      {
        intermediateMessages: [],
        runId: "run-3",
        state: "running",
        userInstruction: "実行中指示",
      },
    ],
    title: "チャット",
  };
}

function completedChatSession(): ChatSession {
  const session = chatSession();
  const latestRun = session.runs[2];
  if (latestRun) {
    session.runs[2] = { ...latestRun, state: "completed" };
  }
  return session;
}

type TestPdfDocument = {
  destroy: () => void;
  getPage: (page: number) => Promise<TestPdfPage>;
  numPages: number;
};

type TestPdfPage = {
  getViewport: (options: { scale: number }) => { height: number; width: number };
  render: () => { cancel: () => void; promise: Promise<void> };
};

function createPdfDocument(numPages: number): TestPdfDocument {
  return {
    destroy: vi.fn(),
    getPage: () => Promise.resolve(createPdfPage()),
    numPages,
  };
}

function createPdfPage(): TestPdfPage {
  return {
    getViewport: ({ scale }) => ({ height: 120 * scale, width: 80 * scale }),
    render: () => ({ cancel: vi.fn(), promise: Promise.resolve() }),
  };
}

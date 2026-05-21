import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPage } from "@/pages/chat/ChatPage";
import type {
  AppConfigResponse,
  ChatHistoryItem,
  ChatRun,
  ChatSession,
  SseEvent,
} from "@/features/chat/model/types";
import type { PdfReference } from "@/features/reference-viewer/model/types";

type StreamChatRunOptions = {
  isCurrent: () => boolean;
  onEvent: (event: SseEvent) => Promise<void> | void;
  sseUrl: string;
};

type RevealSubmittedAnswerOptions = {
  answer: NonNullable<ChatRun["answer"]>;
  isCurrent: () => boolean;
  onAnswerComplete: (runId: string, answer: NonNullable<ChatRun["answer"]>) => void;
  onAnswerChange: (runId: string, answer: NonNullable<ChatRun["answer"]>) => void;
  onAnswerStart: (runId: string, answer: NonNullable<ChatRun["answer"]>) => void;
  onThoughtComplete: (runId: string) => void;
  runId: string;
};

type AcceptedChatResponse = {
  response: { run_id: string; sse_url: string; state: ChatRun["state"] };
  session: ChatSession;
};

type StreamRecord = {
  options: StreamChatRunOptions;
  resolve: () => void;
};

const testState = vi.hoisted(() => ({
  api: {
    appendChatRun: vi.fn<(chatId: string, message: string) => Promise<AcceptedChatResponse>>(),
    cancelChatRun:
      vi.fn<
        (
          chatId: string,
          runId: string,
        ) => Promise<{ run_id: string; state: ChatRun["state"]; user_message: string }>
      >(),
    deleteChat: vi.fn<(chatId: string) => Promise<{ chatId: string; chatState: "削除中" }>>(),
    getActiveChatSession: vi.fn<() => Promise<ChatSession>>(),
    getAppConfig: vi.fn<() => Promise<AppConfigResponse>>(),
    getChatDetail: vi.fn<(chatId: string) => Promise<ChatSession>>(),
    listChatHistories: vi.fn<() => Promise<ChatHistoryItem[]>>(),
    startChat: vi.fn<(message: string) => Promise<AcceptedChatResponse>>(),
    streamChatRun: vi.fn<(options: StreamChatRunOptions) => Promise<void>>(),
  },
  revealSubmittedAnswer: vi.fn<(options: RevealSubmittedAnswerOptions) => Promise<void>>(),
  streams: [] as StreamRecord[],
}));

vi.mock("@/features/chat/api/chatApi", () => ({
  appendChatRun: testState.api.appendChatRun,
  cancelChatRun: testState.api.cancelChatRun,
  deleteChat: testState.api.deleteChat,
  getActiveChatSession: testState.api.getActiveChatSession,
  getAppConfig: testState.api.getAppConfig,
  getChatDetail: testState.api.getChatDetail,
  listChatHistories: testState.api.listChatHistories,
  startChat: testState.api.startChat,
  streamChatRun: testState.api.streamChatRun,
}));

vi.mock("@/features/chat/lib/revealAnswer", () => ({
  revealSubmittedAnswer: testState.revealSubmittedAnswer,
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({
    activeChatId,
    children,
    histories,
    onOpenAnswer,
    onRequestDeleteCurrentChat,
    onRequestDeleteHistoryChat,
    onStartNewChat,
  }: {
    activeChatId?: string;
    children: ReactNode | ((state: { sidebarCollapsed: boolean }) => ReactNode);
    histories: ChatHistoryItem[];
    onOpenAnswer: (chatId: string) => void;
    onRequestDeleteCurrentChat: () => void;
    onRequestDeleteHistoryChat: (chatId: string) => void;
    onStartNewChat: () => void;
  }) => (
    <section>
      <div data-testid="active-chat-id">{activeChatId ?? "none"}</div>
      <div data-testid="history-count">{histories.length}</div>
      <button type="button" onClick={() => onOpenAnswer("chat-history")}>
        履歴を開く
      </button>
      <button type="button" onClick={onStartNewChat}>
        新規チャットへ戻る
      </button>
      <button type="button" onClick={onRequestDeleteCurrentChat}>
        表示中チャットを削除する
      </button>
      <button type="button" onClick={() => onRequestDeleteHistoryChat("chat-other")}>
        履歴項目を削除する
      </button>
      {typeof children === "function" ? children({ sidebarCollapsed: false }) : children}
    </section>
  ),
}));

vi.mock("@/features/chat/components/ChatStartScreen", () => ({
  ChatStartScreen: ({
    inputSuggestions,
    welcomeMessage,
    onStart,
  }: {
    inputSuggestions: string[];
    welcomeMessage?: string;
    onStart: (message: string) => void;
  }) => (
    <section data-testid="start-screen">
      <div>{welcomeMessage ?? "default welcome"}</div>
      <div>{inputSuggestions.join(",") || "候補なし"}</div>
      <button type="button" onClick={() => onStart("新規の依頼")}>
        新規依頼を送信
      </button>
    </section>
  ),
}));

vi.mock("@/features/chat/components/ChatThread", () => ({
  ChatThread: ({
    cancelingRunId,
    openThoughtRunIds,
    scrollReserveRunId,
    scrollTargetRunId,
    session,
    onCancelRun,
    onOpenPdf,
    onScrollTargetHandled,
    onSubmitInstruction,
    onToggleThought,
  }: {
    cancelingRunId?: string | null;
    openThoughtRunIds: Set<string>;
    scrollReserveRunId?: string;
    scrollTargetRunId?: string;
    session: ChatSession;
    onCancelRun: (runId: string) => void;
    onOpenPdf: (reference: PdfReference) => void;
    onScrollTargetHandled: () => void;
    onSubmitInstruction: (message: string) => void;
    onToggleThought: (runId: string) => void;
  }) => {
    const latestRun = session.runs.at(-1);
    const firstRun = session.runs[0];
    const firstReference = session.runs
      .flatMap((run) => run.answer?.blocks.flatMap((block) => block.references) ?? [])
      .find((reference) => reference.source_type === "pdf");

    return (
      <section data-testid="chat-thread">
        <div data-testid="session-id">{session.id}</div>
        <div data-testid="canceling-run-id">{cancelingRunId ?? "none"}</div>
        <div data-testid="open-thoughts">{Array.from(openThoughtRunIds).join(",")}</div>
        <div data-testid="scroll-reserve">{scrollReserveRunId ?? "none"}</div>
        <div data-testid="scroll-target">{scrollTargetRunId ?? "none"}</div>
        {session.runs.map((run) => (
          <article key={run.runId}>
            <div>{run.runId}</div>
            <div>{run.state}</div>
            <div>{run.statusMessage ?? "status none"}</div>
            <div>
              {run.answer?.blocks.map((block) => block.markdown).join("\n") ?? "answer none"}
            </div>
            {run.intermediateMessages.map((message) => (
              <div key={message.id}>{message.text}</div>
            ))}
          </article>
        ))}
        <button type="button" onClick={() => latestRun && onCancelRun(latestRun.runId)}>
          最新runをキャンセル
        </button>
        <button type="button" onClick={() => firstRun && onCancelRun(firstRun.runId)}>
          先頭runをキャンセル
        </button>
        <button type="button" onClick={() => onSubmitInstruction("継続の依頼")}>
          継続依頼を送信
        </button>
        <button type="button" onClick={() => firstRun && onToggleThought(firstRun.runId)}>
          思考表示を切替
        </button>
        <button type="button" onClick={onScrollTargetHandled}>
          スクロール完了
        </button>
        <button type="button" onClick={() => firstReference && onOpenPdf(firstReference)}>
          参照元を開く
        </button>
      </section>
    );
  },
}));

vi.mock("@/features/reference-viewer/components/ReferenceViewerDialog", () => ({
  ReferenceViewerDialog: ({
    open,
    reference,
    onOpenChange,
  }: {
    open: boolean;
    reference: PdfReference | null;
    onOpenChange: (open: boolean) => void;
  }) => (
    <section data-testid="reference-dialog">
      <div>{open ? "PDF表示中" : "PDF非表示"}</div>
      <div>{reference?.label ?? "参照元なし"}</div>
      <button type="button" onClick={() => onOpenChange(false)}>
        PDFを閉じる
      </button>
    </section>
  ),
}));

describe("ChatPage", () => {
  beforeEach(() => {
    testState.streams.length = 0;
    vi.clearAllMocks();
    testState.api.getAppConfig.mockResolvedValue({
      input_suggestions: ["候補A", "候補B"],
      welcome_message: "ようこそ",
    });
    testState.api.listChatHistories.mockResolvedValue([history("chat-history", "履歴")]);
    testState.api.getActiveChatSession.mockResolvedValue(emptySession());
    testState.api.getChatDetail.mockResolvedValue(historySession());
    testState.api.startChat.mockResolvedValue(accepted("chat-new", "run-new", "/sse/new"));
    testState.api.appendChatRun.mockResolvedValue(continuedAccepted());
    testState.api.cancelChatRun.mockResolvedValue({
      run_id: "run-history",
      state: "キャンセル要求中",
      user_message: "キャンセルしています。",
    });
    testState.api.deleteChat.mockResolvedValue({ chatId: "chat-history", chatState: "削除中" });
    testState.api.streamChatRun.mockImplementation(
      (options) =>
        new Promise<void>((resolve) => {
          testState.streams.push({ options, resolve });
        }),
    );
    testState.revealSubmittedAnswer.mockImplementation(async (options) => {
      if (!options.isCurrent()) {
        return;
      }
      options.onThoughtComplete(options.runId);
      options.onAnswerStart(options.runId, {
        blocks: options.answer.blocks.map(() => ({ markdown: "", references: [] })),
      });
      options.onAnswerChange(options.runId, options.answer);
      options.onAnswerComplete(options.runId, options.answer);
    });
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
      writable: true,
    });
  });

  it("観点：初期表示。確認：設定、履歴、アクティブセッションを取得して開始画面へ反映する。", async () => {
    render(<ChatPage />);

    await waitFor(() => expect(screen.getByTestId("start-screen")).toBeInTheDocument());

    expect(testState.api.getAppConfig).toHaveBeenCalledTimes(1);
    expect(testState.api.listChatHistories).toHaveBeenCalledTimes(1);
    expect(testState.api.getActiveChatSession).toHaveBeenCalledTimes(1);
    expect(screen.getByText("ようこそ")).toBeInTheDocument();
    expect(screen.getByText("候補A,候補B")).toBeInTheDocument();
    expect(screen.getByTestId("history-count")).toHaveTextContent("1");
    expect(screen.getByTestId("active-chat-id")).toHaveTextContent("none");
  });

  it("観点：初期表示異常系。確認：設定取得失敗時は開始画面を利用可能な状態にする。", async () => {
    testState.api.getAppConfig.mockRejectedValueOnce(new Error("config failed"));

    render(<ChatPage />);

    await waitFor(() => expect(screen.getByTestId("start-screen")).toBeInTheDocument());
    expect(screen.getByText("default welcome")).toBeInTheDocument();
    expect(screen.getByText("候補なし")).toBeInTheDocument();
  });

  it("観点：履歴一覧異常系。確認：履歴取得失敗時は利用者向けメッセージを表示する。", async () => {
    testState.api.listChatHistories.mockRejectedValueOnce(new Error("history failed"));
    testState.api.getActiveChatSession.mockRejectedValueOnce(new Error("history failed"));

    render(<ChatPage />);

    expect(await screen.findByText("チャット履歴を読み込めませんでした。")).toBeInTheDocument();
    expect(screen.getByTestId("history-count")).toHaveTextContent("0");
  });

  it("観点：初期履歴詳細異常系。確認：直近チャット詳細取得失敗時は履歴を保持してメッセージを表示する。", async () => {
    testState.api.getActiveChatSession.mockRejectedValueOnce(new Error("active detail failed"));

    render(<ChatPage />);

    expect(await screen.findByText("選択したチャットを読み込めませんでした。")).toBeInTheDocument();
    expect(screen.getByTestId("history-count")).toHaveTextContent("1");
    expect(screen.getByTestId("active-chat-id")).toHaveTextContent("none");
  });

  it("観点：初期表示の破棄。確認：初期取得完了前にアンマウントされた場合は表示更新しない。", async () => {
    let resolveConfig: (value: AppConfigResponse) => void = () => undefined;
    let resolveHistories: (value: ChatHistoryItem[]) => void = () => undefined;
    let resolveSession: (value: ChatSession) => void = () => undefined;
    testState.api.getAppConfig.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveConfig = resolve;
      }),
    );
    testState.api.listChatHistories.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveHistories = resolve;
      }),
    );
    testState.api.getActiveChatSession.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSession = resolve;
      }),
    );
    const { unmount } = render(<ChatPage />);

    unmount();
    await act(async () => {
      resolveConfig({ welcome_message: "破棄後" });
      resolveHistories([history("chat-history", "履歴")]);
      resolveSession(emptySession());
    });

    expect(screen.queryByText("破棄後")).not.toBeInTheDocument();
  });

  it("観点：初期表示の競合。確認：初期取得完了前に新規送信した場合は実行中セッションを維持する。", async () => {
    const user = userEvent.setup();
    let resolveInitialSession: (value: ChatSession) => void = () => undefined;
    testState.api.getActiveChatSession.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveInitialSession = resolve;
      }),
    );

    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "新規依頼を送信" }));

    await waitFor(() => expect(testState.streams).toHaveLength(1));
    expect(screen.getByTestId("session-id")).toHaveTextContent("chat-new");
    await emit(0, { event: "message", payload: { run_id: "run-new", text: "作業を開始します。" } });
    expect(screen.getByText("作業を開始します。")).toBeInTheDocument();

    await act(async () => {
      resolveInitialSession(historySession());
    });

    expect(screen.getByTestId("session-id")).toHaveTextContent("chat-new");
    expect(screen.getByText("作業を開始します。")).toBeInTheDocument();
  });

  it("観点：新規チャット開始。確認：受付後にSSE状態、中間、回答、履歴更新、参照元表示へ連携する。", async () => {
    const user = userEvent.setup();
    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "新規依頼を送信" }));

    await waitFor(() => expect(testState.streams).toHaveLength(1));
    expect(testState.api.startChat).toHaveBeenCalledWith("新規の依頼");
    expect(screen.getByTestId("session-id")).toHaveTextContent("chat-new");
    expect(screen.getByTestId("open-thoughts")).toHaveTextContent("run-new");

    await emit(0, { event: "state", payload: { run_id: "run-new", state: "実行中" } });
    await emit(0, { event: "message", payload: { run_id: "run-new", text: "調査中" } });
    testState.api.cancelChatRun.mockResolvedValueOnce({
      run_id: "run-new",
      state: "キャンセル要求中",
      user_message: "キャンセル受付",
    });
    await user.click(screen.getByRole("button", { name: "最新runをキャンセル" }));
    await waitFor(() =>
      expect(screen.getByTestId("canceling-run-id")).toHaveTextContent("run-new"),
    );
    await emit(0, {
      event: "answer",
      payload: {
        answer: { blocks: [{ markdown: "別run回答", references: [] }] },
        run_id: "run-other",
        state: "完了",
      },
    });
    expect(screen.getByTestId("canceling-run-id")).toHaveTextContent("run-new");
    await emit(0, {
      event: "answer",
      payload: {
        answer: { blocks: [{ markdown: "最終回答", references: [reference()] }] },
        run_id: "run-new",
        state: "完了",
      },
    });

    expect(screen.getByText("調査中")).toBeInTheDocument();
    expect(screen.getByText("最終回答")).toBeInTheDocument();
    expect(screen.getByTestId("canceling-run-id")).toHaveTextContent("none");
    expect(screen.getByTestId("open-thoughts")).toHaveTextContent("");

    await act(async () => testState.streams[0]?.resolve());
    await waitFor(() => expect(testState.api.listChatHistories).toHaveBeenCalledTimes(3));

    await user.click(screen.getByRole("button", { name: "参照元を開く" }));
    expect(screen.getByTestId("reference-dialog")).toHaveTextContent("PDF表示中");
    expect(screen.getByTestId("reference-dialog")).toHaveTextContent("資料");
    await user.click(screen.getByRole("button", { name: "PDFを閉じる" }));
    expect(screen.getByTestId("reference-dialog")).toHaveTextContent("PDF非表示");
  });

  it("観点：新規チャット異常系。確認：受付失敗とSSE切断を利用者向けメッセージへ変換する。", async () => {
    const user = userEvent.setup();
    testState.api.startChat.mockRejectedValueOnce(new Error("start failed"));
    render(<ChatPage />);

    await user.click(await screen.findByRole("button", { name: "新規依頼を送信" }));
    expect(
      await screen.findByText(
        "ユーザ指示を受け付けられませんでした。時間を置いて再度お試しください。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("start-screen")).toBeInTheDocument();

    testState.api.startChat.mockResolvedValueOnce(accepted("chat-new", "run-new", "/sse/new"));
    testState.api.streamChatRun.mockRejectedValueOnce(new Error("SSE接続が切断されました。"));
    await user.click(screen.getByRole("button", { name: "新規依頼を送信" }));

    expect(
      await screen.findByText("回答生成中の接続が切れました。再度お試しください。"),
    ).toBeInTheDocument();
    expect(screen.getByText("エラー")).toBeInTheDocument();
  });

  it("観点：履歴と継続指示。確認：履歴詳細表示、思考開閉、継続run追加、スクロール予約を処理する。", async () => {
    const user = userEvent.setup();
    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));

    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history"));
    expect(testState.api.getChatDetail).toHaveBeenCalledWith("chat-history");
    expect(screen.getByTestId("active-chat-id")).toHaveTextContent("chat-history");

    await user.click(screen.getByRole("button", { name: "思考表示を切替" }));
    expect(screen.getByTestId("open-thoughts")).toHaveTextContent("run-history");
    await user.click(screen.getByRole("button", { name: "思考表示を切替" }));
    expect(screen.getByTestId("open-thoughts")).toHaveTextContent("");

    await user.click(screen.getByRole("button", { name: "継続依頼を送信" }));
    await waitFor(() => expect(testState.streams).toHaveLength(1));
    expect(testState.api.appendChatRun).toHaveBeenCalledWith("chat-history", "継続の依頼");
    expect(screen.getByTestId("scroll-reserve")).toHaveTextContent("run-next");
    expect(screen.getByTestId("scroll-target")).toHaveTextContent("run-next");

    await user.click(screen.getByRole("button", { name: "スクロール完了" }));
    expect(screen.getByTestId("scroll-target")).toHaveTextContent("none");

    testState.api.cancelChatRun.mockResolvedValueOnce({
      run_id: "run-next",
      state: "キャンセル要求中",
      user_message: "キャンセル受付",
    });
    await user.click(screen.getByRole("button", { name: "最新runをキャンセル" }));
    await waitFor(() =>
      expect(screen.getByTestId("canceling-run-id")).toHaveTextContent("run-next"),
    );
    await emit(0, {
      event: "error",
      payload: {
        run_id: "run-next",
        state: "エラー",
        user_message: "失敗しました。",
      },
    });
    expect(screen.getByText("失敗しました。")).toBeInTheDocument();

    await emit(0, {
      event: "canceled",
      payload: {
        run_id: "run-next",
        state: "キャンセル済み",
        user_message: "キャンセルしました。",
      },
    });
    expect(screen.getByText("キャンセルしました。")).toBeInTheDocument();
  });

  it("観点：履歴・継続異常系。確認：詳細取得失敗と継続受付失敗を利用者向けメッセージへ変換する。", async () => {
    const user = userEvent.setup();
    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));
    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history"));

    testState.api.getChatDetail.mockRejectedValueOnce(new Error("detail failed"));
    await user.click(screen.getByRole("button", { name: "履歴を開く" }));
    expect(await screen.findByText("選択したチャットを読み込めませんでした。")).toBeInTheDocument();
    expect(screen.getByText("履歴回答")).toBeInTheDocument();

    testState.api.appendChatRun.mockRejectedValueOnce(new Error("append failed"));
    await user.click(screen.getByRole("button", { name: "継続依頼を送信" }));
    expect(
      await screen.findByText(
        "ユーザ指示を受け付けられませんでした。時間を置いて再度お試しください。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("履歴回答")).toBeInTheDocument();
  });

  it("観点：履歴再表示。確認：未完了runを含む履歴を開いた場合は対象SSEへ再接続する。", async () => {
    const user = userEvent.setup();
    testState.api.getChatDetail.mockResolvedValueOnce(runningHistorySession());

    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));

    await waitFor(() => expect(testState.streams).toHaveLength(1));
    expect(testState.streams[0]?.options.sseUrl).toBe(
      "/api/chats/chat-history/runs/run-running/sse",
    );
    expect(screen.getByTestId("open-thoughts")).toHaveTextContent("run-running");

    await emit(0, { event: "message", payload: { run_id: "run-running", text: "保存済み中間" } });
    expect(screen.getAllByText("保存済み中間")).toHaveLength(1);

    await emit(0, { event: "message", payload: { run_id: "run-running", text: "再接続後" } });
    expect(screen.getByText("再接続後")).toBeInTheDocument();

    await emit(0, {
      event: "answer",
      payload: {
        answer: { blocks: [{ markdown: "再接続回答", references: [reference()] }] },
        run_id: "run-running",
        state: "完了",
      },
    });
    expect(screen.getByText("再接続回答")).toBeInTheDocument();

    await act(async () => testState.streams[0]?.resolve());
    await waitFor(() => expect(testState.api.listChatHistories).toHaveBeenCalledTimes(2));
  });

  it("観点：キャンセル。確認：受付成功時の状態反映と受付失敗時のキャンセル中解除を処理する。", async () => {
    const user = userEvent.setup();
    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));
    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history"));

    await user.click(screen.getByRole("button", { name: "最新runをキャンセル" }));
    await waitFor(() =>
      expect(screen.getByTestId("canceling-run-id")).toHaveTextContent("run-history"),
    );
    expect(testState.api.cancelChatRun).toHaveBeenCalledWith("chat-history", "run-history");
    expect(screen.getByText("キャンセルしています。")).toBeInTheDocument();

    testState.api.cancelChatRun.mockRejectedValueOnce(new Error("cancel failed"));
    await user.click(screen.getByRole("button", { name: "最新runをキャンセル" }));
    await waitFor(() => expect(screen.getByTestId("canceling-run-id")).toHaveTextContent("none"));
    expect(
      await screen.findByText("キャンセルできませんでした。処理状態を確認してください。"),
    ).toBeInTheDocument();
  });

  it("観点：表示中チャット削除。確認：確認OK後に削除APIを呼び、開始画面へ戻して履歴を再取得する。", async () => {
    const user = userEvent.setup();
    testState.api.listChatHistories
      .mockResolvedValueOnce([history("chat-history", "履歴")])
      .mockResolvedValueOnce([]);

    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));
    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history"));

    await user.click(screen.getByRole("button", { name: "表示中チャットを削除する" }));
    expect(screen.getByRole("dialog", { name: "チャットを削除しますか？" })).toBeInTheDocument();
    expect(screen.getByText("この操作は取り消せません。")).toBeInTheDocument();
    expect(screen.queryByText(/履歴を削除します。/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "OK" })).toHaveClass(
      "bg-[var(--dc-danger)]",
      "text-white",
    );
    await user.click(screen.getByRole("button", { name: "OK" }));

    await waitFor(() => expect(testState.api.deleteChat).toHaveBeenCalledWith("chat-history"));
    expect(screen.getByTestId("start-screen")).toBeInTheDocument();
    expect(screen.getByTestId("active-chat-id")).toHaveTextContent("none");
    expect(screen.getByTestId("history-count")).toHaveTextContent("0");
  });

  it("観点：履歴項目削除。確認：表示中でない履歴削除時は現在表示中チャットを維持する。", async () => {
    const user = userEvent.setup();
    testState.api.listChatHistories
      .mockResolvedValueOnce([history("chat-history", "表示中"), history("chat-other", "別履歴")])
      .mockResolvedValueOnce([history("chat-history", "表示中")]);
    testState.api.deleteChat.mockResolvedValueOnce({ chatId: "chat-other", chatState: "削除中" });

    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));
    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history"));

    await user.click(screen.getByRole("button", { name: "履歴項目を削除する" }));
    expect(screen.getByRole("dialog", { name: "チャットを削除しますか？" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "OK" }));

    await waitFor(() => expect(testState.api.deleteChat).toHaveBeenCalledWith("chat-other"));
    expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history");
    expect(screen.getByTestId("active-chat-id")).toHaveTextContent("chat-history");
    expect(screen.getByTestId("history-count")).toHaveTextContent("1");
  });

  it("観点：削除中競合。確認：継続指示で削除中を検知した場合は開始画面へ戻す。", async () => {
    const user = userEvent.setup();
    testState.api.appendChatRun.mockRejectedValueOnce(
      Object.assign(new Error("このチャットは削除中のため操作できません。"), {
        status: 409,
      }),
    );
    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));
    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history"));

    await user.click(screen.getByRole("button", { name: "継続依頼を送信" }));

    expect(
      await screen.findByText("このチャットは削除中のため操作できません。"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("start-screen")).toBeInTheDocument();
  });

  it("観点：旧ストリーム化。確認：受付応答前に別操作された場合は開始結果とSSE更新を無視する。", async () => {
    const user = userEvent.setup();
    let resolveStart: (response: AcceptedChatResponse) => void = () => undefined;
    testState.api.startChat.mockReturnValueOnce(
      new Promise<AcceptedChatResponse>((resolve) => {
        resolveStart = resolve;
      }),
    );

    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "新規依頼を送信" }));
    await user.click(screen.getByRole("button", { name: "新規チャットへ戻る" }));

    await act(async () => resolveStart(accepted("chat-late", "run-late", "/sse/late")));
    expect(screen.queryByText("chat-late")).not.toBeInTheDocument();
    expect(testState.streams).toHaveLength(0);
  });

  it("観点：旧ストリーム化。確認：SSE購読後に別操作された場合は終端後の履歴再取得を抑止する。", async () => {
    const user = userEvent.setup();
    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "新規依頼を送信" }));
    await waitFor(() => expect(testState.streams).toHaveLength(1));
    expect(testState.api.listChatHistories).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole("button", { name: "新規チャットへ戻る" }));
    await act(async () => testState.streams[0]?.resolve());

    expect(testState.api.listChatHistories).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("start-screen")).toBeInTheDocument();
  });

  it("観点：回答反映。確認：回答開始前にMarkdown更新が来た場合も参照元を空配列として扱う。", async () => {
    const user = userEvent.setup();
    testState.revealSubmittedAnswer.mockImplementationOnce(async (options) => {
      options.onAnswerChange(options.runId, { blocks: [{ markdown: "先行表示", references: [] }] });
      options.onAnswerComplete(options.runId, options.answer);
    });

    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "新規依頼を送信" }));
    await waitFor(() => expect(testState.streams).toHaveLength(1));
    await emit(0, {
      event: "answer",
      payload: {
        answer: { blocks: [{ markdown: "参照元なし回答", references: [] }] },
        run_id: "run-new",
        state: "完了",
      },
    });

    expect(screen.getByText("参照元なし回答")).toBeInTheDocument();
  });

  it("観点：旧ストリーム化。確認：継続指示の受付応答前に別操作された場合は継続結果を無視する。", async () => {
    const user = userEvent.setup();
    let resolveAppend: (response: AcceptedChatResponse) => void = () => undefined;
    testState.api.appendChatRun.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveAppend = resolve;
      }),
    );

    render(<ChatPage />);
    await user.click(await screen.findByRole("button", { name: "履歴を開く" }));
    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("chat-history"));
    await user.click(screen.getByRole("button", { name: "継続依頼を送信" }));
    await user.click(screen.getByRole("button", { name: "新規チャットへ戻る" }));

    await act(async () => resolveAppend(continuedAccepted()));

    expect(testState.streams).toHaveLength(0);
    expect(screen.getByTestId("start-screen")).toBeInTheDocument();
  });
});

async function emit(index: number, event: SseEvent): Promise<void> {
  const stream = testState.streams[index];
  if (!stream) {
    throw new Error("SSEストリームが開始されていません。");
  }
  await act(async () => {
    await stream.options.onEvent(event);
  });
}

function emptySession(): ChatSession {
  return {
    id: "",
    runs: [],
    title: "",
  };
}

function history(chatId: string, title: string): ChatHistoryItem {
  return {
    chatId,
    latestRunId: `${chatId}-run`,
    latestState: "完了",
    title,
    updatedAt: "2026-05-09T10:00:00+09:00",
  };
}

function accepted(chatId: string, runId: string, sseUrl: string): AcceptedChatResponse {
  return {
    response: {
      run_id: runId,
      sse_url: sseUrl,
      state: "受付",
    },
    session: {
      id: chatId,
      runs: [
        {
          intermediateMessages: [],
          runId,
          state: "受付",
          userInstruction: "指示",
        },
      ],
      title: "チャット",
    },
  };
}

function continuedAccepted(): AcceptedChatResponse {
  return {
    response: {
      run_id: "run-next",
      sse_url: "/sse/next",
      state: "受付",
    },
    session: {
      id: "chat-history",
      runs: [
        {
          answer: { blocks: [{ markdown: "履歴回答", references: [reference()] }] },
          intermediateMessages: [],
          runId: "run-history",
          state: "完了",
          userInstruction: "履歴指示",
        },
        {
          intermediateMessages: [],
          runId: "run-next",
          state: "受付",
          userInstruction: "継続の依頼",
        },
      ],
      title: "履歴",
    },
  };
}

function historySession(): ChatSession {
  return {
    id: "chat-history",
    runs: [
      {
        answer: { blocks: [{ markdown: "履歴回答", references: [reference()] }] },
        intermediateMessages: [],
        runId: "run-history",
        state: "完了",
        userInstruction: "履歴指示",
      },
    ],
    title: "履歴",
  };
}

function runningHistorySession(): ChatSession {
  return {
    id: "chat-history",
    runs: [
      {
        answer: { blocks: [{ markdown: "履歴回答", references: [reference()] }] },
        intermediateMessages: [],
        runId: "run-history",
        state: "完了",
        userInstruction: "履歴指示",
      },
      {
        intermediateMessages: [{ id: "intermediate-1", text: "保存済み中間" }],
        runId: "run-running",
        state: "実行中",
        userInstruction: "継続中指示",
      },
    ],
    title: "履歴",
  };
}

function reference(): PdfReference {
  return {
    label: "資料",
    locator: { page_end: 2, page_start: 1 },
    source_type: "pdf",
    url: "/api/references/ref-1",
  };
}

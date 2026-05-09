import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Providers } from "@/app/providers";
import { ChatPage } from "@/pages/chat/ChatPage";
import type { ChatDetailResponse, SseEvent } from "@/features/chat/model/types";

type JsonResponse = Record<string, unknown> | Record<string, unknown>[];

const mermaidMocks = vi.hoisted(() => ({
  initialize: vi.fn(),
  render: vi.fn<(id: string, source: string) => Promise<{ svg: string }>>(),
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

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: pdfMocks.getDocument,
}));

vi.mock("react-zoom-pan-pinch", () => ({
  TransformComponent: ({ children }: { children: ReactNode }) => (
    <div data-testid="transform-component">{children}</div>
  ),
  TransformWrapper: ({ children }: { children: ReactNode }) => (
    <div data-testid="transform-wrapper">{children}</div>
  ),
  useControls: () => ({
    setTransform: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
  }),
}));

const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const payload = responseByUrl(String(input), init);
  if (payload instanceof Response) {
    return Promise.resolve(payload);
  }
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    }),
  );
});

let continuedAccepted = false;
let cancelShouldFail = false;
let appConfigShouldFail = false;
let historyListShouldFail = false;
let startShouldFail = false;
let detailShouldFail = false;
let appendShouldFail = false;
let runningHistory = false;

describe("ChatPage integration", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    continuedAccepted = false;
    cancelShouldFail = false;
    appConfigShouldFail = false;
    historyListShouldFail = false;
    startShouldFail = false;
    detailShouldFail = false;
    appendShouldFail = false;
    runningHistory = false;
    FakeEventSource.instances = [];
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", FakeEventSource);
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1280,
      writable: true,
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(() => Promise.resolve()) },
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
      () => ({ setTransform: vi.fn() }) as unknown as CanvasRenderingContext2D,
    );
    mermaidMocks.render.mockResolvedValue({
      svg: '<svg viewBox="0 0 120 60"><text>連携図</text></svg>',
    });
    pdfMocks.getDocument.mockReturnValue({ promise: Promise.resolve(createPdfDocument(2)) });
  });

  it("観点：チャット画面連携。確認：開始、SSE、参照元、履歴、継続、キャンセルが画面へ反映される。", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    expect(await screen.findByRole("heading", { name: "ようこそ" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "候補B" }));
    await user.click(screen.getByLabelText("送信"));

    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const firstStream = FakeEventSource.latest();
    await act(async () => {
      firstStream.emit({ event: "state", payload: { run_id: "run-new", state: "実行中" } });
      firstStream.emit({ event: "message", payload: { run_id: "run-new", text: "調査中" } });
      firstStream.emit({
        event: "answer",
        payload: {
          answer: {
            blocks: [
              {
                markdown:
                  "回答本文\n\n```ts\nconst ok = true;\n```\n\n```mermaid\ngraph TD;A-->B;\n```",
                references: [referenceResponse()],
              },
            ],
          },
          run_id: "run-new",
          state: "完了",
        },
      });
      await Promise.resolve();
    });

    expect(await screen.findByText("調査中")).toBeInTheDocument();
    expect(await screen.findByText("回答本文", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByText("連携図", {}, { timeout: 3000 })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /資料 p.1-2/ }, { timeout: 3000 }));
    expect(screen.getByRole("dialog", { name: "資料" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "閉じる" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "資料" })).not.toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "履歴1" }));
    expect(await screen.findByText("履歴回答")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("指示を入力してください"), "継続の依頼");
    await user.click(screen.getByLabelText("送信"));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    const continuedStream = FakeEventSource.latest();
    await act(async () => {
      continuedStream.emit({ event: "state", payload: { run_id: "run-next", state: "実行中" } });
      await Promise.resolve();
    });
    expect(await screen.findByLabelText("キャンセル")).toBeInTheDocument();
    await user.click(screen.getByLabelText("キャンセル"));
    expect(await screen.findByLabelText("キャンセル処理中")).toBeDisabled();

    await act(async () => {
      continuedStream.emit({
        event: "canceled",
        payload: {
          run_id: "run-next",
          state: "キャンセル済み",
          user_message: "キャンセルしました。",
        },
      });
      await Promise.resolve();
    });

    expect(await screen.findByText("キャンセルしました。")).toBeInTheDocument();
  });

  it("観点：異常系連携。確認：キャンセル失敗、SSEエラー、新規開始戻りを画面へ反映する。", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    await user.click(await screen.findByRole("button", { name: "候補A" }));
    await user.click(screen.getByLabelText("送信"));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const stream = FakeEventSource.latest();
    await act(async () => {
      stream.emit({ event: "state", payload: { run_id: "run-new", state: "実行中" } });
      stream.emit({ event: "message", payload: { run_id: "run-new", text: "調査中" } });
      await Promise.resolve();
    });

    await user.click(await screen.findByRole("button", { name: "作業プロセス" }));
    expect(screen.queryByText("調査中")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "作業プロセス" }));
    expect(await screen.findByText("調査中")).toBeInTheDocument();

    cancelShouldFail = true;
    await user.click(await screen.findByLabelText("キャンセル"));
    expect(await screen.findByLabelText("キャンセル")).toBeInTheDocument();

    await act(async () => {
      stream.emit({
        event: "error",
        payload: {
          run_id: "run-new",
          state: "エラー",
          user_message: "失敗しました。",
        },
      });
      await Promise.resolve();
    });
    expect(await screen.findByText("失敗しました。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /新しいチャット/ }));
    expect(await screen.findByRole("heading", { name: "ようこそ" })).toBeInTheDocument();
  });

  it("観点：初期取得異常連携。確認：設定取得失敗は開始可能な初期画面、履歴一覧失敗はエラー表示へ反映する。", async () => {
    appConfigShouldFail = true;
    historyListShouldFail = true;

    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    expect(await screen.findByText("チャット履歴を読み込めませんでした。")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("指示を入力してください")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ようこそ" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "候補A" })).not.toBeInTheDocument();
  });

  it("観点：初期履歴詳細異常連携。確認：履歴一覧取得後の直近詳細失敗を画面へ反映する。", async () => {
    detailShouldFail = true;

    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    expect(await screen.findByText("選択したチャットを読み込めませんでした。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ようこそ" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "履歴1" })).toBeInTheDocument();
  });

  it("観点：受付異常連携。確認：新規開始失敗、継続受付失敗、SSE切断を画面へ反映する。", async () => {
    const user = userEvent.setup();
    startShouldFail = true;

    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    await user.click(await screen.findByRole("button", { name: "候補A" }));
    await user.click(screen.getByLabelText("送信"));
    expect(
      await screen.findByText(
        "ユーザ指示を受け付けられませんでした。時間を置いて再度お試しください。",
      ),
    ).toBeInTheDocument();

    startShouldFail = false;
    await user.click(screen.getByRole("button", { name: "候補A" }));
    await user.click(screen.getByLabelText("送信"));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const stream = FakeEventSource.latest();
    await act(async () => {
      stream.onerror?.(new Event("error"));
      await Promise.resolve();
    });
    expect(
      await screen.findByText("回答生成中の接続が切れました。再度お試しください。"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "履歴1" }));
    appendShouldFail = true;
    await user.type(screen.getByPlaceholderText("指示を入力してください"), "継続の依頼");
    await user.click(screen.getByLabelText("送信"));
    expect(
      await screen.findByText(
        "ユーザ指示を受け付けられませんでした。時間を置いて再度お試しください。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("履歴回答")).toBeInTheDocument();
  });

  it("観点：履歴詳細異常連携。確認：履歴詳細取得失敗を既存表示を保ったまま画面へ反映する。", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    expect(await screen.findByRole("heading", { name: "ようこそ" })).toBeInTheDocument();
    detailShouldFail = true;
    await user.click(screen.getByRole("button", { name: "履歴1" }));
    expect(await screen.findByText("選択したチャットを読み込めませんでした。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ようこそ" })).toBeInTheDocument();
  });

  it("観点：履歴再表示連携。確認：未完了runを含む履歴を開くとSSEへ再接続する。", async () => {
    const user = userEvent.setup();
    runningHistory = true;

    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    await user.click(await screen.findByRole("button", { name: "履歴1" }));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    expect(String(FakeEventSource.latest().url)).toBe(
      "/api/chats/chat-history/runs/run-running/sse",
    );

    await act(async () => {
      FakeEventSource.latest().emit({
        event: "message",
        payload: { run_id: "run-running", text: "保存済み中間" },
      });
      FakeEventSource.latest().emit({
        event: "message",
        payload: { run_id: "run-running", text: "再接続中" },
      });
      FakeEventSource.latest().emit({
        event: "answer",
        payload: {
          answer: { blocks: [{ markdown: "履歴再接続回答", references: [referenceResponse()] }] },
          run_id: "run-running",
          state: "完了",
        },
      });
      await Promise.resolve();
    });

    expect(await screen.findByText("保存済み中間")).toBeInTheDocument();
    expect(screen.getAllByText("保存済み中間")).toHaveLength(1);
    expect(await screen.findByText("再接続中")).toBeInTheDocument();
    expect(await screen.findByText("履歴再接続回答", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("観点：初期表示破棄。確認：初期取得完了前に破棄された場合は画面更新しない。", async () => {
    let resolveConfig: () => void = () => undefined;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveConfig = () =>
            resolve(
              new Response(JSON.stringify({ welcome_message: "破棄後" }), {
                headers: { "Content-Type": "application/json" },
                status: 200,
              }),
            );
        }),
    );
    const { unmount } = render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    unmount();
    await act(async () => resolveConfig());

    expect(screen.queryByText("破棄後")).not.toBeInTheDocument();
  });

  it("観点：初期表示競合連携。確認：初期取得完了前に送信した場合は実行中セッションを維持する。", async () => {
    const user = userEvent.setup();
    let resolveInitialDetail: () => void = () => undefined;
    let shouldDelayInitialDetail = true;
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/chats/chat-history" && shouldDelayInitialDetail) {
        shouldDelayInitialDetail = false;
        return new Promise<Response>((resolve) => {
          resolveInitialDetail = () =>
            resolve(
              new Response(
                JSON.stringify(chatDetail("chat-history", "run-history", "履歴指示", "履歴回答")),
                {
                  headers: { "Content-Type": "application/json" },
                  status: 200,
                },
              ),
            );
        });
      }
      const payload = responseByUrl(url, init);
      if (payload instanceof Response) {
        return Promise.resolve(payload);
      }
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
      );
    });

    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    await user.type(screen.getByPlaceholderText("指示を入力してください"), "候補B");
    await user.click(screen.getByLabelText("送信"));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    await act(async () => {
      FakeEventSource.latest().emit({
        event: "message",
        payload: { run_id: "run-new", text: "作業を開始します。" },
      });
      await Promise.resolve();
    });

    expect(await screen.findByText("作業を開始します。")).toBeInTheDocument();
    await act(async () => resolveInitialDetail());

    expect(screen.getByText("作業を開始します。")).toBeInTheDocument();
    expect(screen.queryByText("履歴回答")).not.toBeInTheDocument();
  });

  it("観点：回答終端連携。確認：キャンセル中runの回答終端でキャンセル中表示を解除し参照元なし回答を表示する。", async () => {
    const user = userEvent.setup();
    render(
      <Providers>
        <ChatPage />
      </Providers>,
    );

    await user.click(await screen.findByRole("button", { name: "候補A" }));
    await user.click(screen.getByLabelText("送信"));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const stream = FakeEventSource.latest();
    await act(async () => {
      stream.emit({ event: "state", payload: { run_id: "run-new", state: "実行中" } });
      await Promise.resolve();
    });
    await user.click(await screen.findByLabelText("キャンセル"));
    expect(await screen.findByLabelText("キャンセル処理中")).toBeDisabled();

    await act(async () => {
      stream.emit({
        event: "answer",
        payload: {
          answer: { blocks: [{ markdown: "参照元なし回答", references: [] }] },
          run_id: "run-new",
          state: "完了",
        },
      });
      await Promise.resolve();
    });

    expect(await screen.findByText("参照元なし回答", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByLabelText("送信")).toBeDisabled();
  });
});

function responseByUrl(url: string, init?: RequestInit): JsonResponse | Response {
  if (url === "/api/app-config") {
    if (appConfigShouldFail) {
      return new Response("error", { status: 500 });
    }
    return { input_suggestions: ["候補A", "候補B"], welcome_message: "ようこそ" };
  }
  if (url === "/api/chat-histories") {
    if (historyListShouldFail) {
      return new Response("error", { status: 500 });
    }
    return [
      {
        chat_id: "chat-history",
        latest_run_id: "run-history",
        latest_state: "完了",
        title: "履歴1",
        updated_at: "2026-05-09T10:00:00+09:00",
      },
    ];
  }
  if (url === "/api/chats/start") {
    expect(["候補A", "候補B"]).toContain(parseStartRequest(init?.body).user_instruction);
    if (startShouldFail) {
      return new Response("error", { status: 500 });
    }
    return { chat_id: "chat-new", run_id: "run-new", sse_url: "/sse/new", state: "受付" };
  }
  if (url === "/api/chats/chat-new/runs/run-new/cancel") {
    if (cancelShouldFail) {
      return new Response("error", { status: 500 });
    }
    return {
      run_id: "run-new",
      state: "キャンセル要求中",
      user_message: "キャンセルしています。",
    };
  }
  if (url === "/api/chats/chat-history/runs") {
    expect(init?.body).toBe(JSON.stringify({ user_instruction: "継続の依頼" }));
    if (appendShouldFail) {
      return new Response("error", { status: 500 });
    }
    continuedAccepted = true;
    return {
      chat_id: "chat-history",
      run_id: "run-next",
      sse_url: "/sse/next",
      state: "受付",
    };
  }
  if (url === "/api/chats/chat-history/runs/run-next/cancel") {
    if (cancelShouldFail) {
      return new Response("error", { status: 500 });
    }
    return {
      run_id: "run-next",
      state: "キャンセル要求中",
      user_message: "キャンセルしています。",
    };
  }
  if (url === "/api/chats/chat-new") {
    return chatDetail("chat-new", "run-new", "候補B", "answer none");
  }
  if (url === "/api/chats/chat-history" && continuedAccepted) {
    return continuedChatDetail();
  }
  if (url === "/api/chats/chat-history" && runningHistory) {
    return runningChatDetail();
  }
  if (url === "/api/chats/chat-history" && detailShouldFail) {
    return new Response("error", { status: 500 });
  }
  return chatDetail("chat-history", "run-history", "履歴指示", "履歴回答");
}

type StartRequest = {
  user_instruction: string;
};

function parseStartRequest(body: BodyInit | null | undefined): StartRequest {
  const parsed: unknown = JSON.parse(String(body));
  if (
    typeof parsed === "object" &&
    parsed !== null &&
    "user_instruction" in parsed &&
    typeof parsed.user_instruction === "string"
  ) {
    return { user_instruction: parsed.user_instruction };
  }
  throw new Error("開始リクエストpayloadが不正です。");
}

function chatDetail(
  chatId: string,
  runId: string,
  userInstruction: string,
  markdown: string,
): ChatDetailResponse {
  return {
    chat_id: chatId,
    runs: [
      {
        answer:
          markdown === "answer none"
            ? undefined
            : { blocks: [{ markdown, references: [referenceResponse()] }] },
        intermediate_messages: [],
        run_id: runId,
        state: "完了",
        user_instruction: userInstruction,
      },
    ],
    title: "チャット",
  };
}

function referenceResponse() {
  return {
    label: "資料",
    locator: { page_end: 2, page_start: 1 },
    source_type: "pdf" as const,
    url: "/api/references/ref-1",
  };
}

function continuedChatDetail(): ChatDetailResponse {
  return {
    chat_id: "chat-history",
    runs: [
      {
        answer: { blocks: [{ markdown: "履歴回答", references: [referenceResponse()] }] },
        intermediate_messages: [],
        run_id: "run-history",
        state: "完了",
        user_instruction: "履歴指示",
      },
      {
        intermediate_messages: [],
        run_id: "run-next",
        state: "受付",
        user_instruction: "継続の依頼",
      },
    ],
    title: "チャット",
  };
}

function runningChatDetail(): ChatDetailResponse {
  return {
    chat_id: "chat-history",
    runs: [
      {
        answer: { blocks: [{ markdown: "履歴回答", references: [referenceResponse()] }] },
        intermediate_messages: [],
        run_id: "run-history",
        state: "完了",
        user_instruction: "履歴指示",
      },
      {
        intermediate_messages: [{ text: "保存済み中間" }],
        run_id: "run-running",
        state: "実行中",
        user_instruction: "継続中指示",
      },
    ],
    title: "チャット",
  };
}

class FakeEventSource extends EventTarget {
  static instances: FakeEventSource[] = [];
  onerror: ((event: Event) => void) | null = null;

  constructor(readonly url: string | URL) {
    super();
    FakeEventSource.instances.push(this);
  }

  static latest(): FakeEventSource {
    const source = FakeEventSource.instances.at(-1);
    if (!source) {
      throw new Error("SSE接続が作成されていません。");
    }
    return source;
  }

  close(): void {}

  emit(event: SseEvent): void {
    this.dispatchEvent(new MessageEvent(event.event, { data: JSON.stringify(event.payload) }));
  }
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

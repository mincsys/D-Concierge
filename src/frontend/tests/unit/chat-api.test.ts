import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  appendChatRun,
  cancelChatRun,
  deleteChat,
  getActiveChatSession,
  getAppConfig,
  getChatDetail,
  listChatHistories,
  startChat,
  streamChatRun,
  toChatHistoryItem,
} from "@/features/chat/api/chatApi";
import type {
  ChatDetailResponse,
  ChatHistoryResponseItem,
  SseEvent,
} from "@/features/chat/model/types";

type JsonResponse = Record<string, unknown> | Record<string, unknown>[];

const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = String(input);
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

describe("chatApi", () => {
  beforeEach(() => {
    fetchMock.mockClear();
    FakeEventSource.instances = [];
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("観点：API応答変換。確認：設定、履歴、詳細、開始、継続、キャンセルを画面モデルへ変換する。", async () => {
    await expect(getAppConfig()).resolves.toEqual({
      welcome_message: "ようこそ",
      input_suggestions: ["要約"],
    });

    await expect(listChatHistories()).resolves.toEqual([
      {
        chatId: "chat-1",
        latestRunId: "run-1",
        latestState: "完了",
        title: "履歴1",
        updatedAt: "2026-05-09T10:00:00+09:00",
      },
    ]);
    await expect(getActiveChatSession()).resolves.toMatchObject({
      id: "chat-1",
      runs: [{ answer: { blocks: [{ markdown: "回答" }] }, runId: "run-1" }],
    });
    await expect(getChatDetail("chat-1")).resolves.toMatchObject({
      id: "chat-1",
      runs: [{ intermediateMessages: [{ id: "intermediate-1", text: "調査中" }] }],
    });
    await expect(startChat(" 初回 ")).resolves.toMatchObject({
      response: { chat_id: "chat-2", run_id: "run-2" },
      session: { id: "chat-2" },
    });
    await expect(appendChatRun("chat-1", "追加")).resolves.toMatchObject({
      response: { chat_id: "chat-1", run_id: "run-3" },
      session: { id: "chat-1" },
    });
    await expect(cancelChatRun("chat-1", "run-1")).resolves.toEqual({
      run_id: "run-1",
      state: "キャンセル要求中",
      user_message: "処理をキャンセルしています。",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chats/start",
      expect.objectContaining({
        body: JSON.stringify({ user_instruction: " 初回 " }),
        method: "POST",
      }),
    );
  });

  it("観点：履歴なし。確認：アクティブ履歴がない場合は空セッションを返す。", async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(
        new Response("[]", {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
      ),
    );

    await expect(getActiveChatSession()).resolves.toEqual({
      id: "",
      runs: [],
      title: "",
    });
  });

  it("観点：API異常系。確認：HTTPエラーは例外にする。", async () => {
    fetchMock.mockResolvedValueOnce(new Response("error", { status: 500 }));

    await expect(getAppConfig()).rejects.toThrow("API request failed: 500");
  });

  it("観点：チャット削除API。確認：DELETEを送信し、削除受付応答を画面モデルへ変換する。", async () => {
    await expect(deleteChat("chat-1")).resolves.toEqual({
      chatId: "chat-1",
      chatState: "削除中",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chats/chat-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("観点：削除中・削除済み競合。確認：HTTPエラー応答の利用者向けメッセージを保持する。", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: "conflict",
          message: "このチャットは削除中のため操作できません。",
        }),
        { headers: { "Content-Type": "application/json" }, status: 409 },
      ),
    );

    await expect(getChatDetail("chat-deleting")).rejects.toMatchObject({
      message: "このチャットは削除中のため操作できません。",
      status: 409,
    });
  });

  it("観点：詳細応答の任意項目。確認：中間メッセージ、回答、参照元が欠落しても画面モデルへ変換する。", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          chat_id: "chat-empty",
          runs: [
            {
              run_id: "run-empty",
              state: "完了",
              user_instruction: "指示",
            },
            {
              answer: { blocks: [{ markdown: "回答" }] },
              run_id: "run-answer",
              state: "完了",
              user_instruction: "指示2",
            },
          ],
          title: "空項目",
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );

    await expect(getChatDetail("chat-empty")).resolves.toEqual({
      id: "chat-empty",
      runs: [
        {
          answer: undefined,
          intermediateMessages: [],
          runId: "run-empty",
          state: "完了",
          statusMessage: undefined,
          userInstruction: "指示",
        },
        {
          answer: { blocks: [{ markdown: "回答", references: [] }] },
          intermediateMessages: [],
          runId: "run-answer",
          state: "完了",
          statusMessage: undefined,
          userInstruction: "指示2",
        },
      ],
      title: "空項目",
    });
  });

  it("観点：SSE処理。確認：終端イベント受信時点で接続を閉じ、イベント処理完了まで待機する。", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const events: SseEvent[] = [];
    let completeAnswerHandler: () => void = () => undefined;
    const streaming = streamChatRun({
      isCurrent: () => true,
      onEvent: (event) => {
        events.push(event);
        if (event.event === "answer") {
          return new Promise<void>((resolve) => {
            completeAnswerHandler = resolve;
          });
        }
      },
      sseUrl: "/api/sse",
    });
    const eventSource = FakeEventSource.latest();

    eventSource.emit("state", { run_id: "run-1", state: "実行中" });
    eventSource.emit("message", { run_id: "run-1", text: "調査中" });
    eventSource.emit("answer", {
      answer: { blocks: [{ markdown: "回答", references: [] }] },
      run_id: "run-1",
      state: "完了",
    });

    expect(eventSource.closed).toBe(true);
    await flushMicrotasks();
    expect(events.map((event) => event.event)).toEqual(["state", "message", "answer"]);

    completeAnswerHandler();
    await expect(streaming).resolves.toBeUndefined();

    expect(eventSource.closed).toBe(true);
  });

  it("観点：SSE切断。確認：終端前の接続断は例外、終端後または旧ストリーム化は正常終了にする。", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const broken = streamChatRun({
      isCurrent: () => true,
      onEvent: () => undefined,
      sseUrl: "/api/sse-error",
    });
    FakeEventSource.latest().fail();
    await expect(broken).rejects.toThrow("SSE接続が切断されました。");

    const stale = streamChatRun({
      isCurrent: () => false,
      onEvent: () => {
        throw new Error("呼ばれない");
      },
      sseUrl: "/api/sse-stale",
    });
    FakeEventSource.latest().emit("state", { run_id: "run-1", state: "実行中" });
    await expect(stale).resolves.toBeUndefined();
  });

  it("観点：SSE終端イベント。確認：error/canceledイベントと終端後onerrorを正常終了として扱う。", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const events: SseEvent[] = [];
    const errorStream = streamChatRun({
      isCurrent: () => true,
      onEvent: (event) => {
        events.push(event);
      },
      sseUrl: "/api/sse-error-event",
    });
    const errorSource = FakeEventSource.latest();

    errorSource.emit("error", {
      run_id: "run-1",
      state: "エラー",
      user_message: "失敗しました。",
    });
    errorSource.fail();
    await expect(errorStream).resolves.toBeUndefined();

    const canceledStream = streamChatRun({
      isCurrent: () => true,
      onEvent: (event) => {
        events.push(event);
      },
      sseUrl: "/api/sse-canceled-event",
    });
    const canceledSource = FakeEventSource.latest();
    canceledSource.emit("canceled", {
      run_id: "run-2",
      state: "キャンセル済み",
      user_message: "キャンセルしました。",
    });
    canceledSource.emit("answer", {
      answer: { blocks: [{ markdown: "完了後の回答", references: [] }] },
      run_id: "run-2",
      state: "完了",
    });
    canceledSource.emit("state", { run_id: "run-2", state: "実行中" });
    await expect(canceledStream).resolves.toBeUndefined();

    expect(events.map((event) => event.event)).toEqual(["error", "canceled"]);
  });

  it("観点：SSE error通知。確認：空データのerrorイベントとonerror上のSSE payloadを区別する。", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const streaming = streamChatRun({
      isCurrent: () => true,
      onEvent: () => undefined,
      sseUrl: "/api/sse-empty-error",
    });
    const eventSource = FakeEventSource.latest();

    eventSource.dispatchEvent(new MessageEvent("error", { data: "" }));
    eventSource.onerror?.(
      new MessageEvent("error", {
        data: JSON.stringify({
          run_id: "run-1",
          state: "エラー",
          user_message: "SSE payload",
        }),
      }),
    );
    eventSource.fail();

    await expect(streaming).rejects.toThrow("SSE接続が切断されました。");
  });

  it("観点：SSEイベント処理例外。確認：イベント処理失敗は例外に変換する。", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const streaming = streamChatRun({
      isCurrent: () => true,
      onEvent: () => {
        throw new Error("handler failed");
      },
      sseUrl: "/api/sse-handler-error",
    });
    FakeEventSource.latest().emit("state", { run_id: "run-1", state: "実行中" });

    await expect(streaming).rejects.toThrow("handler failed");
  });

  it("観点：SSEイベント処理例外。確認：非Errorの処理失敗とsettled後の切断を安全に扱う。", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const streaming = streamChatRun({
      isCurrent: () => true,
      onEvent: () => {
        throw "handler failed";
      },
      sseUrl: "/api/sse-non-error",
    });
    const eventSource = FakeEventSource.latest();
    eventSource.emit("message", { run_id: "run-1", text: "調査中" });
    eventSource.emit("message", { run_id: "run-1", text: "継続調査" });

    await expect(streaming).rejects.toThrow("SSEイベントの処理に失敗しました。");
    eventSource.fail();
  });

  it("観点：履歴変換。確認：snake_caseの履歴項目をcamelCaseへ変換する。", () => {
    const item: ChatHistoryResponseItem = {
      chat_id: "chat-1",
      latest_state: "受付",
      title: "履歴",
      updated_at: "2026-05-09T10:00:00+09:00",
    };

    expect(toChatHistoryItem(item)).toEqual({
      chatId: "chat-1",
      latestRunId: undefined,
      latestState: "受付",
      title: "履歴",
      updatedAt: "2026-05-09T10:00:00+09:00",
    });
  });
});

function responseByUrl(url: string, init?: RequestInit): JsonResponse | Response {
  if (url === "/api/app-config") {
    return { input_suggestions: ["要約"], welcome_message: "ようこそ" };
  }
  if (url === "/api/chat-histories") {
    return [
      {
        chat_id: "chat-1",
        latest_run_id: "run-1",
        latest_state: "完了",
        title: "履歴1",
        updated_at: "2026-05-09T10:00:00+09:00",
      },
    ];
  }
  if (url === "/api/chats/start") {
    expect(init?.body).toBe(JSON.stringify({ user_instruction: " 初回 " }));
    return { chat_id: "chat-2", run_id: "run-2", sse_url: "/sse/run-2", state: "受付" };
  }
  if (url === "/api/chats/chat-1/runs") {
    return { chat_id: "chat-1", run_id: "run-3", sse_url: "/sse/run-3", state: "受付" };
  }
  if (url === "/api/chats/chat-1/runs/run-1/cancel") {
    return {
      run_id: "run-1",
      state: "キャンセル要求中",
      user_message: "処理をキャンセルしています。",
    };
  }
  if (url === "/api/chats/chat-1" && init?.method === "DELETE") {
    return { chat_id: "chat-1", chat_state: "削除中" };
  }
  if (url === "/api/chats/chat-2") {
    return chatDetail("chat-2", "run-2");
  }
  return chatDetail("chat-1", "run-1");
}

function chatDetail(chatId: string, runId: string): ChatDetailResponse {
  return {
    chat_id: chatId,
    runs: [
      {
        answer: {
          blocks: [
            {
              markdown: "回答",
              references: [
                {
                  label: "資料",
                  locator: { page_end: 2, page_start: 1 },
                  source_type: "pdf",
                  url: "/api/references/ref-1",
                },
              ],
            },
          ],
        },
        intermediate_messages: [{ text: "調査中" }],
        run_id: runId,
        state: "完了",
        user_instruction: "指示",
      },
    ],
    title: "履歴",
  };
}

class FakeEventSource extends EventTarget {
  static instances: FakeEventSource[] = [];
  closed = false;
  onerror: ((event: Event) => void) | null = null;
  readonly url: string;

  constructor(url: string | URL) {
    super();
    this.url = String(url);
    FakeEventSource.instances.push(this);
  }

  static latest(): FakeEventSource {
    const eventSource = FakeEventSource.instances.at(-1);
    if (!eventSource) {
      throw new Error("EventSourceが生成されていません。");
    }
    return eventSource;
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, payload: unknown): void {
    this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(payload) }));
  }

  fail(): void {
    this.onerror?.(new Event("error"));
  }
}

async function flushMicrotasks() {
  for (let index = 0; index < 8; index += 1) {
    await Promise.resolve();
  }
}

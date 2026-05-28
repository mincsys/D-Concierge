import type {
  AnswerResponse,
  AppConfigResponse,
  CancelChatRunResponse,
  ChatDetailResponse,
  ChatHistoryItem,
  ChatHistoryResponseItem,
  ChatRun,
  ChatRunResponse,
  ChatSession,
  ChatStartResponse,
  DeletedChat,
  DeleteChatResponse,
  IntermediateMessageResponse,
  SseEvent,
} from "@/features/chat/model/types";

type AcceptedChatRun = {
  response: ChatStartResponse;
  session: ChatSession;
};

type StreamChatRunOptions = {
  sseUrl: string;
  isCurrent: () => boolean;
  onEvent: (event: SseEvent) => Promise<void> | void;
  signal?: AbortSignal;
};

export class ChatApiError extends Error {
  readonly error?: string;
  readonly status: number;

  constructor(status: number, message: string, error?: string) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
    this.error = error;
  }
}

export async function getAppConfig(): Promise<AppConfigResponse> {
  return requestJson<AppConfigResponse>("/api/app-config");
}

export async function listChatHistories(): Promise<ChatHistoryItem[]> {
  const histories = await requestJson<ChatHistoryResponseItem[]>("/api/chat-histories");
  return histories.map(toChatHistoryItem);
}

export async function getActiveChatSession(): Promise<ChatSession> {
  const histories = await listChatHistories();
  const activeChatId = histories[0]?.chatId;
  if (!activeChatId) {
    return {
      id: "",
      title: "",
      runs: [],
    };
  }
  return getChatDetail(activeChatId);
}

export async function getChatDetail(chatId: string): Promise<ChatSession> {
  return toChatSession(await requestJson<ChatDetailResponse>(`/api/chats/${chatId}`));
}

export async function startChat(userInstruction: string): Promise<AcceptedChatRun> {
  const response = await requestJson<ChatStartResponse>("/api/chats/start", {
    method: "POST",
    body: JSON.stringify({ user_instruction: userInstruction }),
  });

  return {
    response,
    session: await getChatDetail(response.chat_id),
  };
}

export async function appendChatRun(
  chatId: string,
  userInstruction: string,
): Promise<AcceptedChatRun> {
  const response = await requestJson<ChatStartResponse>(`/api/chats/${chatId}/runs`, {
    method: "POST",
    body: JSON.stringify({ user_instruction: userInstruction }),
  });

  return {
    response,
    session: await getChatDetail(response.chat_id),
  };
}

export async function cancelChatRun(chatId: string, runId: string): Promise<CancelChatRunResponse> {
  return requestJson<CancelChatRunResponse>(`/api/chats/${chatId}/runs/${runId}/cancel`, {
    method: "POST",
  });
}

export async function deleteChat(chatId: string): Promise<DeletedChat> {
  const response = await requestJson<DeleteChatResponse>(`/api/chats/${chatId}`, {
    method: "DELETE",
  });
  return {
    chatId: response.chat_id,
    chatState: response.chat_state,
  };
}

export function streamChatRun({ sseUrl, isCurrent, onEvent, signal }: StreamChatRunOptions) {
  if (signal?.aborted) {
    return Promise.resolve();
  }

  return new Promise<void>((resolve, reject) => {
    const eventSource = new EventSource(sseUrl);
    let settled = false;
    let terminalEventReceived = false;
    let eventChain = Promise.resolve();

    function settleAsResolved() {
      if (settled) {
        return;
      }
      settled = true;
      signal?.removeEventListener("abort", settleAsResolved);
      eventSource.close();
      resolve();
    }

    function settleAsRejected(error: Error) {
      if (settled) {
        return;
      }
      settled = true;
      signal?.removeEventListener("abort", settleAsResolved);
      eventSource.close();
      reject(error);
    }

    function enqueueEvent(event: SseEvent) {
      if (settled || terminalEventReceived) {
        return;
      }

      const terminalEvent = isTerminalSseEvent(event);
      if (terminalEvent) {
        terminalEventReceived = true;
        eventSource.close();
      }

      eventChain = eventChain
        .then(async () => {
          if (!isCurrent()) {
            settleAsResolved();
            return;
          }

          await onEvent(event);

          if (terminalEvent) {
            settleAsResolved();
          }
        })
        .catch((error: unknown) => {
          settleAsRejected(
            error instanceof Error ? error : new Error("SSEイベントの処理に失敗しました。"),
          );
        });
    }

    eventSource.addEventListener("state", (event) => enqueueEvent(parseSseEvent("state", event)));
    eventSource.addEventListener("message", (event) =>
      enqueueEvent(parseSseEvent("message", event)),
    );
    eventSource.addEventListener("answer", (event) => enqueueEvent(parseSseEvent("answer", event)));
    eventSource.addEventListener("error", (event) => {
      if (
        event instanceof MessageEvent &&
        typeof event.data === "string" &&
        event.data.length > 0
      ) {
        enqueueEvent(parseSseEvent("error", event));
      }
    });
    eventSource.addEventListener("canceled", (event) =>
      enqueueEvent(parseSseEvent("canceled", event)),
    );

    eventSource.onerror = (event) => {
      if (
        event instanceof MessageEvent &&
        typeof event.data === "string" &&
        event.data.length > 0
      ) {
        return;
      }

      if (terminalEventReceived) {
        return;
      }

      if (!settled) {
        settleAsRejected(new Error("SSE接続が切断されました。"));
      }
    };

    signal?.addEventListener("abort", settleAsResolved, { once: true });
    if (signal?.aborted) {
      settleAsResolved();
    }
  });
}

function isTerminalSseEvent(event: SseEvent) {
  return event.event === "answer" || event.event === "error" || event.event === "canceled";
}

export function toChatHistoryItem(item: ChatHistoryResponseItem): ChatHistoryItem {
  return {
    chatId: item.chat_id,
    title: item.title,
    latestRunId: item.latest_run_id,
    latestState: item.latest_state,
    updatedAt: item.updated_at,
  };
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);
    throw new ChatApiError(
      response.status,
      payload?.message ?? `API request failed: ${response.status}`,
      payload?.error,
    );
  }

  return response.json() as Promise<T>;
}

async function parseErrorPayload(
  response: Response,
): Promise<{ error?: string; message?: string } | null> {
  try {
    const payload: unknown = await response.json();
    if (payload === null || typeof payload !== "object") {
      return null;
    }
    const error =
      "error" in payload && typeof payload.error === "string" ? payload.error : undefined;
    const message =
      "message" in payload && typeof payload.message === "string" ? payload.message : undefined;
    return { error, message };
  } catch {
    return null;
  }
}

function parseSseEvent(eventName: SseEvent["event"], event: MessageEvent<string>): SseEvent {
  return {
    event: eventName,
    payload: JSON.parse(event.data) as SseEvent["payload"],
  } as SseEvent;
}

function toChatSession(response: ChatDetailResponse): ChatSession {
  return {
    id: response.chat_id,
    title: response.title,
    runs: response.runs.map(toChatRun),
  };
}

function toChatRun(run: ChatRunResponse): ChatRun {
  return {
    runId: run.run_id,
    state: run.state,
    userInstruction: run.user_instruction,
    intermediateMessages: (run.intermediate_messages ?? []).map(toIntermediateMessage),
    answer: run.answer ? toAnswer(run.answer) : undefined,
    statusMessage: run.user_message,
  };
}

function toIntermediateMessage(message: IntermediateMessageResponse, index: number) {
  return {
    id: `intermediate-${index + 1}`,
    text: message.text,
  };
}

function toAnswer(answer: AnswerResponse) {
  return {
    blocks: answer.blocks.map((block) => ({
      markdown: block.markdown,
      references: block.references ?? [],
    })),
  };
}

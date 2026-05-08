import type {
  AnswerResponse,
  AppConfigResponse,
  ChatDetailResponse,
  ChatHistoryItem,
  ChatHistoryResponseItem,
  ChatRun,
  ChatRunResponse,
  ChatSession,
  ChatStartResponse,
  IntermediateMessageResponse,
  SseEvent,
} from "@/features/chat/model/types";
import {
  acceptStubContinuedRun,
  acceptStubStartChat,
  applyStubSseEvent,
  getStubActiveChatDetail,
  getStubAppConfig,
  getStubChatDetail,
  listStubChatHistories,
  listStubSseEvents,
} from "@/stub/chatStubRuntime";

const ARTIFACT_URLS: Record<string, string> = {
  "/api/artifacts/6a9158c3-ae1c-4a13-9494-940df193ceef": "/api/artifacts/6a9158c3-ae1c-4a13-9494-940df193ceef.svg",
};
const SSE_EVENT_DELAY_MS = 420;

type AcceptedChatRun = {
  response: ChatStartResponse;
  session: ChatSession;
};

type StreamChatRunOptions = {
  runId: string;
  isCurrent: () => boolean;
  onEvent: (event: SseEvent) => Promise<void> | void;
};

export async function getAppConfig(): Promise<AppConfigResponse> {
  return getStubAppConfig();
}

export async function listChatHistories(): Promise<ChatHistoryItem[]> {
  return listStubChatHistories().map(toChatHistoryItem);
}

export async function getActiveChatSession(): Promise<ChatSession> {
  return toChatSession(getStubActiveChatDetail());
}

export async function getChatDetail(chatId: string): Promise<ChatSession> {
  return toChatSession(getStubChatDetail(chatId));
}

export async function startChat(userInstruction: string): Promise<AcceptedChatRun> {
  const accepted = acceptStubStartChat(userInstruction);

  return {
    response: accepted.response,
    session: toChatSession(accepted.detail),
  };
}

export async function appendChatRun(chatId: string, userInstruction: string): Promise<AcceptedChatRun> {
  const accepted = acceptStubContinuedRun(chatId, userInstruction);

  return {
    response: accepted.response,
    session: toChatSession(accepted.detail),
  };
}

export async function streamChatRun({
  runId,
  isCurrent,
  onEvent,
}: StreamChatRunOptions) {
  for (const event of listStubSseEvents(runId)) {
    if (!isCurrent()) {
      return;
    }

    applyStubSseEvent(event);
    const resolvedEvent = resolveSseEvent(event);
    await onEvent(resolvedEvent);
    await delay(SSE_EVENT_DELAY_MS);
  }
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
    markdown: resolveArtifactUrls(answer.markdown),
    references: answer.references ?? [],
  };
}

function resolveSseEvent(event: SseEvent): SseEvent {
  if (event.event !== "answer") {
    return event;
  }

  return {
    ...event,
    payload: {
      ...event.payload,
      answer: {
        ...event.payload.answer,
        markdown: resolveArtifactUrls(event.payload.answer.markdown),
        references: event.payload.answer.references ?? [],
      },
    },
  };
}

function resolveArtifactUrls(markdown: string) {
  return Object.entries(ARTIFACT_URLS).reduce(
    (currentMarkdown, [contractUrl, displayUrl]) =>
      currentMarkdown.replace(new RegExp(`${escapeRegExp(contractUrl)}(?!\\.svg)`, "g"), displayUrl),
    markdown,
  );
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

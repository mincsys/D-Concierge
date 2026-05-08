import type {
  AppConfigResponse,
  ChatDetailResponse,
  ChatHistoryResponseItem,
  ChatRun,
  ChatRunResponse,
  ChatStartResponse,
  SseEvent,
} from "@/features/chat/model/types";
import { stubAppConfig, stubChatDetails, stubChatHistories, stubSseEvents } from "@/stub/chatStub";

const FALLBACK_STREAM_RUN_ID = "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2";
const FALLBACK_HISTORY_RUN_ID = "811cc3ac-c48a-4f20-a42c-0e2ea51b5930";

let runtimeChatHistories: ChatHistoryResponseItem[] = [...stubChatHistories];
let runtimeChatDetails: Record<string, ChatDetailResponse> = { ...stubChatDetails };

export function getStubAppConfig(): AppConfigResponse {
  return stubAppConfig;
}

export function listStubChatHistories(): ChatHistoryResponseItem[] {
  return runtimeChatHistories;
}

export function getStubActiveChatDetail(): ChatDetailResponse {
  const chatId = runtimeChatHistories[0]?.chat_id;
  return getStubChatDetail(chatId ?? createUuid());
}

export function getStubChatDetail(chatId: string): ChatDetailResponse {
  return runtimeChatDetails[chatId] ?? createFallbackChatDetail(chatId);
}

export function acceptStubStartChat(userInstruction: string) {
  const chatId = createUuid();
  const runId = createUuid();
  const title = createChatTitle(userInstruction);
  const response = createAcceptedResponse(chatId, runId);
  const detail: ChatDetailResponse = {
    chat_id: chatId,
    title,
    runs: [createAcceptedRun(response.run_id, userInstruction)],
  };

  runtimeChatDetails = {
    ...runtimeChatDetails,
    [chatId]: detail,
  };
  upsertRuntimeHistory({
    chat_id: chatId,
    title,
    latest_run_id: runId,
    latest_state: response.state,
    updated_at: currentIsoString(),
  });

  return { response, detail };
}

export function acceptStubContinuedRun(chatId: string, userInstruction: string) {
  const runId = createUuid();
  const response = createAcceptedResponse(chatId, runId);
  const currentDetail = getStubChatDetail(chatId);
  const nextDetail: ChatDetailResponse = {
    ...currentDetail,
    runs: [...currentDetail.runs, createAcceptedRun(response.run_id, userInstruction)],
  };

  runtimeChatDetails = {
    ...runtimeChatDetails,
    [chatId]: nextDetail,
  };
  upsertRuntimeHistory({
    chat_id: chatId,
    title: currentDetail.title,
    latest_run_id: response.run_id,
    latest_state: response.state,
    updated_at: currentIsoString(),
  });

  return { response, detail: nextDetail };
}

export function listStubSseEvents(runId: string): SseEvent[] {
  const events = stubSseEvents[runId] ?? stubSseEvents[FALLBACK_STREAM_RUN_ID] ?? [];
  return events.map((event) => assignRunIdToSseEvent(event, runId));
}

export function applyStubSseEvent(event: SseEvent) {
  const chatId = findChatIdByRunId(event.payload.run_id);
  if (!chatId) {
    return;
  }

  const currentDetail = runtimeChatDetails[chatId];
  if (!currentDetail) {
    return;
  }

  const nextDetail: ChatDetailResponse = {
    ...currentDetail,
    runs: currentDetail.runs.map((run) => applyEventToRun(run, event)),
  };

  runtimeChatDetails = {
    ...runtimeChatDetails,
    [chatId]: nextDetail,
  };

  const latestRun = nextDetail.runs.at(-1);
  if (latestRun) {
    upsertRuntimeHistory({
      chat_id: chatId,
      title: nextDetail.title,
      latest_run_id: latestRun.run_id,
      latest_state: latestRun.state,
      updated_at: isTerminalState(latestRun.state) ? currentIsoString() : getHistoryUpdatedAt(chatId),
    });
  }
}

function createAcceptedResponse(chatId: string, runId: string): ChatStartResponse {
  return {
    chat_id: chatId,
    run_id: runId,
    sse_url: `/api/chats/${chatId}/runs/${runId}/sse`,
    state: "受付",
  };
}

function createAcceptedRun(runId: string, userInstruction: string): ChatRunResponse {
  return {
    run_id: runId,
    state: "受付",
    user_instruction: userInstruction,
    intermediate_messages: [],
  };
}

function assignRunIdToSseEvent(event: SseEvent, runId: string): SseEvent {
  switch (event.event) {
    case "state":
      return {
        event: event.event,
        payload: {
          ...event.payload,
          run_id: runId,
        },
      };
    case "message":
      return {
        event: event.event,
        payload: {
          ...event.payload,
          run_id: runId,
        },
      };
    case "answer":
      return {
        event: event.event,
        payload: {
          ...event.payload,
          run_id: runId,
        },
      };
    case "error":
      return {
        event: event.event,
        payload: {
          ...event.payload,
          run_id: runId,
        },
      };
    case "canceled":
      return {
        event: event.event,
        payload: {
          ...event.payload,
          run_id: runId,
        },
      };
  }
}

function applyEventToRun(run: ChatRunResponse, event: SseEvent): ChatRunResponse {
  if (run.run_id !== event.payload.run_id) {
    return run;
  }

  switch (event.event) {
    case "state":
      return {
        ...run,
        state: event.payload.state,
      };
    case "message":
      return {
        ...run,
        intermediate_messages: [...(run.intermediate_messages ?? []), { text: event.payload.text }],
      };
    case "answer":
      return {
        ...run,
        state: event.payload.state,
        answer: event.payload.answer,
      };
    case "error":
    case "canceled":
      return {
        ...run,
        state: event.payload.state,
        user_message: event.payload.user_message,
      };
  }
}

function upsertRuntimeHistory(item: ChatHistoryResponseItem) {
  runtimeChatHistories = [
    item,
    ...runtimeChatHistories.filter((history) => history.chat_id !== item.chat_id),
  ].sort((left, right) => right.updated_at.localeCompare(left.updated_at));
}

function findChatIdByRunId(runId: string) {
  return Object.values(runtimeChatDetails).find((detail) =>
    detail.runs.some((run) => run.run_id === runId),
  )?.chat_id;
}

function getHistoryUpdatedAt(chatId: string) {
  return runtimeChatHistories.find((history) => history.chat_id === chatId)?.updated_at ?? currentIsoString();
}

function createFallbackChatDetail(chatId: string): ChatDetailResponse {
  const history = runtimeChatHistories.find((item) => item.chat_id === chatId);
  const runId = history?.latest_run_id ?? FALLBACK_HISTORY_RUN_ID;
  const title = history?.title ?? "保存済みチャット";

  return {
    chat_id: chatId,
    title,
    runs: [
      {
        run_id: runId,
        state: "完了",
        user_instruction: `${title}について整理して`,
        intermediate_messages: [
          { text: "保存済み履歴を読み込みました。" },
          { text: "回答本文と参照元を復元します。" },
        ],
        answer: {
          markdown: `${title}の保存済み回答です。履歴詳細取得APIのレスポンスをもとに再表示しています。`,
          references: [],
        },
      },
    ],
  };
}

function createChatTitle(userInstruction: string) {
  const normalized = userInstruction.replace(/\s+/g, " ").trim();
  return normalized.length > 0 ? normalized.slice(0, 50) : "新しいチャット";
}

function isTerminalState(state: ChatRun["state"]) {
  return state === "完了" || state === "キャンセル済み" || state === "エラー" || state === "タイムアウト";
}

function createUuid() {
  return crypto.randomUUID();
}

function currentIsoString() {
  return new Date().toISOString();
}

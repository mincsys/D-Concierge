import type {
  AppConfigResponse,
  CancelChatRunResponse,
  ChatDetailResponse,
  ChatHistoryResponseItem,
  ChatRun,
  ChatRunResponse,
  ChatStartResponse,
  SseEvent,
} from "../../src/features/chat/model/types";
import { randomUUID } from "node:crypto";
import { stubAppConfig, stubChatDetails, stubChatHistories, stubSseEvents } from "../data/chatData";

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

export function cancelStubRun(runId: string) {
  const chatId = findChatIdByRunId(runId);
  if (!chatId) {
    throw new Error("cancel target not found");
  }

  const currentDetail = runtimeChatDetails[chatId];
  const targetRun = currentDetail?.runs.find((run) => run.run_id === runId);
  if (!currentDetail || !targetRun || !isCancelableState(targetRun.state)) {
    throw new Error("cancel target is not cancelable");
  }

  const response: CancelChatRunResponse = {
    run_id: runId,
    state: "キャンセル要求中",
    user_message: "処理をキャンセルしています。",
  };

  runtimeChatDetails = {
    ...runtimeChatDetails,
    [chatId]: {
      ...currentDetail,
      runs: currentDetail.runs.map((run) =>
        run.run_id === runId
          ? {
              ...run,
              state: response.state,
              user_message: response.user_message,
            }
          : run,
      ),
    },
  };

  upsertRuntimeHistory({
    chat_id: chatId,
    title: currentDetail.title,
    latest_run_id: runId,
    latest_state: response.state,
    updated_at: getHistoryUpdatedAt(chatId),
  });

  return response;
}

export function isStubRunCancelRequested(runId: string) {
  const chatId = findChatIdByRunId(runId);
  const run = chatId ? runtimeChatDetails[chatId]?.runs.find((item) => item.run_id === runId) : undefined;
  return run?.state === "キャンセル要求中";
}

export function createStubCanceledEvent(runId: string): SseEvent {
  return {
    event: "canceled",
    payload: {
      run_id: runId,
      state: "キャンセル済み",
      user_message: "処理をキャンセルしました。",
    },
  };
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
      if (run.state === "キャンセル要求中" && event.payload.state !== "キャンセル済み") {
        return run;
      }
      return {
        ...run,
        state: event.payload.state,
      };
    case "message":
      if (run.state === "キャンセル要求中" || isTerminalState(run.state)) {
        return run;
      }
      return {
        ...run,
        intermediate_messages: [...(run.intermediate_messages ?? []), { text: event.payload.text }],
      };
    case "answer":
      if (run.state === "キャンセル要求中" || isTerminalState(run.state)) {
        return run;
      }
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

function isCancelableState(state: ChatRun["state"]) {
  return state === "受付" || state === "実行中" || state === "検証中";
}

function createUuid() {
  return randomUUID();
}

function currentIsoString() {
  return new Date().toISOString();
}

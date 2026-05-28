import { v7 as uuidv7 } from "uuid";

import type {
  AccountUserResponse,
  ChangePasswordRequest,
  DeleteAccountResponse,
  LoginRequest,
  RegisterAccountRequest,
} from "../../src/features/account/model/types";
import type {
  AppConfigResponse,
  CancelChatRunResponse,
  ChatDetailResponse,
  ChatHistoryResponseItem,
  ChatRun,
  ChatRunResponse,
  ChatStartResponse,
  DeleteChatResponse,
  SseEvent,
} from "../../src/features/chat/model/types";
import { stubAppConfig, stubChatDetails, stubChatHistories, stubSseEvents } from "../data/chatData";

const FALLBACK_STREAM_RUN_ID = "5f5e8cf2-25f6-4962-9d1d-c3c93ab6cbb2";
const FALLBACK_HISTORY_RUN_ID = "811cc3ac-c48a-4f20-a42c-0e2ea51b5930";
const DEMO_USER_ID = "demo-user";
const DEMO_PASSWORD = "password";

type RuntimeUser = {
  userId: string;
  userName: string;
  password: string;
};

type RuntimeChatStore = {
  histories: ChatHistoryResponseItem[];
  details: Record<string, ChatDetailResponse>;
};

type ValidationResult = {
  error: "validation_error";
  message: string;
  field_errors: Partial<Record<SnakeFieldErrorKey, string>>;
};

type SnakeFieldErrorKey =
  | "user_id"
  | "user_name"
  | "password"
  | "password_confirmation"
  | "current_password"
  | "new_password"
  | "new_password_confirmation";

let defaultSessionId: string | null = null;
let defaultSessionIssued = false;
let runtimeUsers: Record<string, RuntimeUser> = {
  [DEMO_USER_ID]: {
    password: DEMO_PASSWORD,
    userId: DEMO_USER_ID,
    userName: "デモユーザ",
  },
};
let runtimeSessions: Record<string, string> = {};
let runtimeChatStores: Record<string, RuntimeChatStore> = {
  [DEMO_USER_ID]: {
    details: { ...stubChatDetails },
    histories: [...stubChatHistories],
  },
};

export function getStubAppConfig(): AppConfigResponse {
  return stubAppConfig;
}

export function getAuthenticatedUser(sessionId: string | undefined): AccountUserResponse | null {
  const user = getRuntimeUserBySession(sessionId);
  return user ? toAccountUserResponse(user) : null;
}

export function issueDefaultSession(): { response: AccountUserResponse; sessionId: string } | null {
  if (defaultSessionIssued) {
    const activeDefaultUserId = defaultSessionId ? runtimeSessions[defaultSessionId] : undefined;
    const activeDefaultUser = activeDefaultUserId ? runtimeUsers[activeDefaultUserId] : undefined;
    return activeDefaultUser && defaultSessionId
      ? { response: toAccountUserResponse(activeDefaultUser), sessionId: defaultSessionId }
      : null;
  }

  const user = runtimeUsers[DEMO_USER_ID];
  if (!user) {
    return null;
  }

  defaultSessionIssued = true;
  const sessionId = createSession(user.userId);
  defaultSessionId = sessionId;
  return { response: toAccountUserResponse(user), sessionId };
}

export function registerStubAccount(
  request: RegisterAccountRequest,
  currentSessionId: string | undefined,
) {
  const fieldErrors = validateUserId(request.userId);
  validateUserName(request.userName, fieldErrors);
  validatePassword(request.password, "password", fieldErrors);
  if (request.password !== request.passwordConfirmation) {
    fieldErrors.password_confirmation = "パスワード確認が一致しません。";
  }
  if (runtimeUsers[request.userId]) {
    fieldErrors.user_id = "このユーザIDは既に使用されています。";
  }

  assertNoValidationErrors(fieldErrors);

  runtimeUsers = {
    ...runtimeUsers,
    [request.userId]: {
      password: request.password,
      userId: request.userId,
      userName: request.userName,
    },
  };
  runtimeChatStores = {
    ...runtimeChatStores,
    [request.userId]: { details: {}, histories: [] },
  };
  const sessionId = replaceSession(currentSessionId, request.userId);
  return { response: toAccountUserResponse(runtimeUsers[request.userId]), sessionId };
}

export function loginStubAccount(request: LoginRequest, currentSessionId: string | undefined) {
  const user = runtimeUsers[request.userId];
  if (!user) {
    throwValidationError({ user_id: "ユーザIDが存在しません。" });
  }
  if (user.password !== request.password) {
    throwValidationError({ password: "パスワードが正しくありません。" });
  }

  const sessionId = replaceSession(currentSessionId, user.userId);
  return { response: toAccountUserResponse(user), sessionId };
}

export function logoutStubSession(sessionId: string | undefined) {
  if (sessionId) {
    const nextSessions = { ...runtimeSessions };
    delete nextSessions[sessionId];
    runtimeSessions = nextSessions;
  }
}

export function changeStubUserName(sessionId: string | undefined, userName: string) {
  const user = requireRuntimeUser(sessionId);
  const fieldErrors: Partial<Record<SnakeFieldErrorKey, string>> = {};
  validateUserName(userName, fieldErrors);
  assertNoValidationErrors(fieldErrors);

  const nextUser = { ...user, userName };
  runtimeUsers = { ...runtimeUsers, [user.userId]: nextUser };
  return toAccountUserResponse(nextUser);
}

export function changeStubPassword(sessionId: string | undefined, request: ChangePasswordRequest) {
  const user = requireRuntimeUser(sessionId);
  const fieldErrors: Partial<Record<SnakeFieldErrorKey, string>> = {};
  if (user.password !== request.currentPassword) {
    fieldErrors.current_password = "現在のパスワードが正しくありません。";
  }
  validatePassword(request.newPassword, "new_password", fieldErrors);
  if (request.newPassword !== request.newPasswordConfirmation) {
    fieldErrors.new_password_confirmation = "新しいパスワード確認が一致しません。";
  }
  assertNoValidationErrors(fieldErrors);

  runtimeUsers = { ...runtimeUsers, [user.userId]: { ...user, password: request.newPassword } };
}

export function deleteStubAccount(sessionId: string | undefined): DeleteAccountResponse {
  const user = requireRuntimeUser(sessionId);
  const nextUsers = { ...runtimeUsers };
  delete nextUsers[user.userId];
  runtimeUsers = nextUsers;

  runtimeSessions = Object.fromEntries(
    Object.entries(runtimeSessions).filter((entry) => entry[1] !== user.userId),
  );

  const nextStores = { ...runtimeChatStores };
  delete nextStores[user.userId];
  runtimeChatStores = nextStores;

  return { account_state: "deleting" };
}

export function listStubChatHistories(userId: string): ChatHistoryResponseItem[] {
  return getChatStore(userId).histories;
}

export function getStubActiveChatDetail(userId: string): ChatDetailResponse {
  const store = getChatStore(userId);
  const chatId = store.histories[0]?.chat_id;
  return getStubChatDetail(userId, chatId ?? createUuid());
}

export function getStubChatDetail(userId: string, chatId: string): ChatDetailResponse {
  const store = getChatStore(userId);
  return store.details[chatId] ?? createFallbackChatDetail(userId, chatId);
}

export function deleteStubChat(userId: string, chatId: string): DeleteChatResponse {
  const store = getChatStore(userId);
  const exists = store.details[chatId] || store.histories.some((item) => item.chat_id === chatId);
  if (!exists) {
    throw new Error("chat not found");
  }

  setChatStore(userId, {
    details: Object.fromEntries(
      Object.entries(store.details).filter((entry) => entry[0] !== chatId),
    ),
    histories: store.histories.filter((history) => history.chat_id !== chatId),
  });

  return {
    chat_id: chatId,
    chat_state: "deleting",
  };
}

export function acceptStubStartChat(userId: string, userInstruction: string) {
  const chatId = createUuid();
  const runId = createUuid();
  const title = createChatTitle(userInstruction);
  const response = createAcceptedResponse(chatId, runId);
  const detail: ChatDetailResponse = {
    chat_id: chatId,
    title,
    runs: [createAcceptedRun(response.run_id, userInstruction)],
  };

  const store = getChatStore(userId);
  setChatStore(userId, {
    details: { ...store.details, [chatId]: detail },
    histories: upsertRuntimeHistory(store.histories, {
      chat_id: chatId,
      title,
      latest_run_id: runId,
      latest_state: response.state,
      updated_at: currentIsoString(),
    }),
  });

  return { response, detail };
}

export function acceptStubContinuedRun(userId: string, chatId: string, userInstruction: string) {
  const runId = createUuid();
  const response = createAcceptedResponse(chatId, runId);
  const currentDetail = getStubChatDetail(userId, chatId);
  const nextDetail: ChatDetailResponse = {
    ...currentDetail,
    runs: [...currentDetail.runs, createAcceptedRun(response.run_id, userInstruction)],
  };
  const store = getChatStore(userId);

  setChatStore(userId, {
    details: { ...store.details, [chatId]: nextDetail },
    histories: upsertRuntimeHistory(store.histories, {
      chat_id: chatId,
      title: currentDetail.title,
      latest_run_id: response.run_id,
      latest_state: response.state,
      updated_at: currentIsoString(),
    }),
  });

  return { response, detail: nextDetail };
}

export function listStubSseEvents(runId: string): SseEvent[] {
  const events = stubSseEvents[runId] ?? stubSseEvents[FALLBACK_STREAM_RUN_ID] ?? [];
  return events.map((event) => assignRunIdToSseEvent(event, runId));
}

export function applyStubSseEvent(userId: string, event: SseEvent) {
  const chatId = findChatIdByRunId(userId, event.payload.run_id);
  if (!chatId) {
    return;
  }

  const store = getChatStore(userId);
  const currentDetail = store.details[chatId];
  if (!currentDetail) {
    return;
  }

  const nextDetail: ChatDetailResponse = {
    ...currentDetail,
    runs: currentDetail.runs.map((run) => applyEventToRun(run, event)),
  };

  const latestRun = nextDetail.runs.at(-1);
  setChatStore(userId, {
    details: { ...store.details, [chatId]: nextDetail },
    histories: latestRun
      ? upsertRuntimeHistory(store.histories, {
          chat_id: chatId,
          title: nextDetail.title,
          latest_run_id: latestRun.run_id,
          latest_state: latestRun.state,
          updated_at: isTerminalState(latestRun.state)
            ? currentIsoString()
            : getHistoryUpdatedAt(userId, chatId),
        })
      : store.histories,
  });
}

export function cancelStubRun(userId: string, runId: string) {
  const chatId = findChatIdByRunId(userId, runId);
  if (!chatId) {
    throw new Error("cancel target not found");
  }

  const store = getChatStore(userId);
  const currentDetail = store.details[chatId];
  const targetRun = currentDetail?.runs.find((run) => run.run_id === runId);
  if (!currentDetail || !targetRun || !isCancelableState(targetRun.state)) {
    throw new Error("cancel target is not cancelable");
  }

  const response: CancelChatRunResponse = {
    run_id: runId,
    state: "cancel_requested",
    user_message: "処理をキャンセルしています。",
  };

  const nextDetail: ChatDetailResponse = {
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
  };

  setChatStore(userId, {
    details: { ...store.details, [chatId]: nextDetail },
    histories: upsertRuntimeHistory(store.histories, {
      chat_id: chatId,
      title: currentDetail.title,
      latest_run_id: runId,
      latest_state: response.state,
      updated_at: getHistoryUpdatedAt(userId, chatId),
    }),
  });

  return response;
}

export function isStubRunCancelRequested(userId: string, runId: string) {
  const chatId = findChatIdByRunId(userId, runId);
  const run = chatId
    ? getChatStore(userId).details[chatId]?.runs.find((item) => item.run_id === runId)
    : undefined;
  return run?.state === "cancel_requested";
}

export function createStubCanceledEvent(runId: string): SseEvent {
  return {
    event: "canceled",
    payload: {
      run_id: runId,
      state: "canceled",
      user_message: "処理をキャンセルしました。",
    },
  };
}

function getRuntimeUserBySession(sessionId: string | undefined) {
  const userId = sessionId ? runtimeSessions[sessionId] : undefined;
  return userId ? runtimeUsers[userId] : undefined;
}

function requireRuntimeUser(sessionId: string | undefined) {
  const user = getRuntimeUserBySession(sessionId);
  if (!user) {
    throw new Error("unauthorized");
  }
  return user;
}

function createSession(userId: string) {
  const sessionId = createUuid();
  runtimeSessions = { ...runtimeSessions, [sessionId]: userId };
  return sessionId;
}

function replaceSession(currentSessionId: string | undefined, userId: string) {
  logoutStubSession(currentSessionId);
  return createSession(userId);
}

function toAccountUserResponse(user: RuntimeUser): AccountUserResponse {
  return {
    user: {
      user_id: user.userId,
      user_name: user.userName,
    },
  };
}

function validateUserId(userId: string): Partial<Record<SnakeFieldErrorKey, string>> {
  const fieldErrors: Partial<Record<SnakeFieldErrorKey, string>> = {};
  if (userId.length < 1 || userId.length > 30) {
    fieldErrors.user_id = "ユーザIDは1文字以上30文字以内で入力してください。";
    return fieldErrors;
  }
  if (!/^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,28}[A-Za-z0-9])?$/.test(userId)) {
    fieldErrors.user_id =
      "ユーザIDは半角英数字、_、-のみを使用し、記号で始めたり終えたりしないでください。";
  }
  return fieldErrors;
}

function validateUserName(
  userName: string,
  fieldErrors: Partial<Record<SnakeFieldErrorKey, string>>,
) {
  if (userName.length < 1 || userName.length > 30) {
    fieldErrors.user_name = "ユーザ名は1文字以上30文字以内で入力してください。";
  }
}

function validatePassword(
  password: string,
  key: "password" | "new_password",
  fieldErrors: Partial<Record<SnakeFieldErrorKey, string>>,
) {
  if (!/^[\x21-\x7E]{5,30}$/.test(password)) {
    fieldErrors[key] = "パスワードは5文字以上30文字以内の半角英字・数字・記号で入力してください。";
  }
}

function assertNoValidationErrors(fieldErrors: Partial<Record<SnakeFieldErrorKey, string>>) {
  if (Object.keys(fieldErrors).length > 0) {
    throwValidationError(fieldErrors);
  }
}

function throwValidationError(fieldErrors: Partial<Record<SnakeFieldErrorKey, string>>): never {
  const result: ValidationResult = {
    error: "validation_error",
    field_errors: fieldErrors,
    message: "入力内容を確認してください。",
  };
  throw result;
}

function getChatStore(userId: string): RuntimeChatStore {
  const store = runtimeChatStores[userId];
  if (store) {
    return store;
  }
  const emptyStore = { details: {}, histories: [] };
  runtimeChatStores = { ...runtimeChatStores, [userId]: emptyStore };
  return emptyStore;
}

function setChatStore(userId: string, store: RuntimeChatStore) {
  runtimeChatStores = { ...runtimeChatStores, [userId]: store };
}

function createAcceptedResponse(chatId: string, runId: string): ChatStartResponse {
  return {
    chat_id: chatId,
    run_id: runId,
    sse_url: `/api/chats/${chatId}/runs/${runId}/sse`,
    state: "accepted",
  };
}

function createAcceptedRun(runId: string, userInstruction: string): ChatRunResponse {
  return {
    run_id: runId,
    state: "accepted",
    user_instruction: userInstruction,
    intermediate_messages: [],
  };
}

function assignRunIdToSseEvent(event: SseEvent, runId: string): SseEvent {
  switch (event.event) {
    case "state":
    case "message":
    case "answer":
    case "error":
    case "canceled":
      return {
        event: event.event,
        payload: {
          ...event.payload,
          run_id: runId,
        },
      } as SseEvent;
  }
}

function applyEventToRun(run: ChatRunResponse, event: SseEvent): ChatRunResponse {
  if (run.run_id !== event.payload.run_id) {
    return run;
  }

  switch (event.event) {
    case "state":
      if (run.state === "cancel_requested" && event.payload.state !== "canceled") {
        return run;
      }
      return {
        ...run,
        state: event.payload.state,
      };
    case "message":
      if (run.state === "cancel_requested" || isTerminalState(run.state)) {
        return run;
      }
      return {
        ...run,
        intermediate_messages: [...(run.intermediate_messages ?? []), { text: event.payload.text }],
      };
    case "answer":
      if (run.state === "cancel_requested" || isTerminalState(run.state)) {
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

function upsertRuntimeHistory(histories: ChatHistoryResponseItem[], item: ChatHistoryResponseItem) {
  return [item, ...histories.filter((history) => history.chat_id !== item.chat_id)].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  );
}

function findChatIdByRunId(userId: string, runId: string) {
  return Object.values(getChatStore(userId).details).find((detail) =>
    detail.runs.some((run) => run.run_id === runId),
  )?.chat_id;
}

function getHistoryUpdatedAt(userId: string, chatId: string) {
  return (
    getChatStore(userId).histories.find((history) => history.chat_id === chatId)?.updated_at ??
    currentIsoString()
  );
}

function createFallbackChatDetail(userId: string, chatId: string): ChatDetailResponse {
  const history = getChatStore(userId).histories.find((item) => item.chat_id === chatId);
  const runId = history?.latest_run_id ?? FALLBACK_HISTORY_RUN_ID;
  const title = history?.title ?? "保存済みチャット";

  return {
    chat_id: chatId,
    title,
    runs: [
      {
        run_id: runId,
        state: "completed",
        user_instruction: `${title}について整理して`,
        intermediate_messages: [
          { text: "保存済み履歴を読み込みました。" },
          { text: "回答本文と参照元を復元します。" },
        ],
        answer: {
          blocks: [
            {
              markdown: `${title}の保存済み回答です。履歴詳細取得APIのレスポンスをもとに再表示しています。`,
              references: [],
            },
          ],
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
  return (
    state === "completed" || state === "canceled" || state === "error" || state === "timed_out"
  );
}

function isCancelableState(state: ChatRun["state"]) {
  return state === "accepted" || state === "running" || state === "validating";
}

function createUuid() {
  return uuidv7();
}

function currentIsoString() {
  return new Date().toISOString();
}

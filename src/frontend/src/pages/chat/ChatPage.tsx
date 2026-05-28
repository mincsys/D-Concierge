import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
} from "@/features/chat/api/chatApi";
import type { AccountUser } from "@/features/account/model/types";
import { ChatStartScreen } from "@/features/chat/components/ChatStartScreen";
import { ChatThread } from "@/features/chat/components/ChatThread";
import { revealSubmittedAnswer } from "@/features/chat/lib/revealAnswer";
import type {
  AppConfigResponse,
  ChatAnswer,
  ChatHistoryItem,
  ChatRun,
  ChatRunState,
  ChatSession,
  SseEvent,
  ViewMode,
} from "@/features/chat/model/types";
import { ReferenceViewerDialog } from "@/features/reference-viewer/components/ReferenceViewerDialog";
import type { PdfReference } from "@/features/reference-viewer/model/types";

const ACCEPTANCE_FAILED_MESSAGE =
  "ユーザ指示を受け付けられませんでした。時間を置いて再度お試しください。";
const SSE_DISCONNECTED_MESSAGE = "回答生成中の接続が切れました。再度お試しください。";
const CANCEL_FAILED_MESSAGE = "キャンセルできませんでした。処理状態を確認してください。";
const HISTORY_LIST_FAILED_MESSAGE = "チャット履歴を読み込めませんでした。";
const HISTORY_DETAIL_FAILED_MESSAGE = "選択したチャットを読み込めませんでした。";
const CHAT_DELETE_FAILED_MESSAGE =
  "チャットを削除できませんでした。時間を置いて再度お試しください。";
const CHAT_DELETING_MESSAGE = "このチャットは削除中のため操作できません。";
const CHAT_DELETED_MESSAGE = "このチャットは削除されました。";

type DeleteTarget = {
  chatId: string;
  title: string;
};

const DEFAULT_DISPLAY_USER: AccountUser = {
  userId: "demo-user",
  userName: "デモユーザ",
};

export function ChatPage({
  currentUser = DEFAULT_DISPLAY_USER,
  onOpenAccountSettings,
  onUnauthorized,
}: {
  currentUser?: AccountUser;
  onOpenAccountSettings?: () => void;
  onUnauthorized?: () => void;
} = {}) {
  const [mode, setMode] = useState<ViewMode>("start");
  const [appConfig, setAppConfig] = useState<AppConfigResponse>({});
  const [histories, setHistories] = useState<ChatHistoryItem[]>([]);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [systemMessage, setSystemMessage] = useState<string | null>(null);
  const [reference, setReference] = useState<PdfReference | null>(null);
  const [openThoughtRunIds, setOpenThoughtRunIds] = useState<Set<string>>(() => new Set());
  const [pdfOpen, setPdfOpen] = useState(false);
  const [cancelingRunId, setCancelingRunId] = useState<string | null>(null);
  const [scrollTargetRunId, setScrollTargetRunId] = useState<string | undefined>();
  const [scrollReserveRunId, setScrollReserveRunId] = useState<string | undefined>();
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const streamRunIdRef = useRef(0);
  const streamAbortControllerRef = useRef<AbortController | null>(null);
  const handleUnauthorizedError = useCallback(
    (error: unknown) => {
      if (statusOf(error) !== 401) {
        return false;
      }
      streamAbortControllerRef.current?.abort();
      streamAbortControllerRef.current = null;
      streamRunIdRef.current += 1;
      onUnauthorized?.();
      return true;
    },
    [onUnauthorized],
  );

  useEffect(() => {
    let cancelled = false;
    const initialStreamId = streamRunIdRef.current;

    async function loadInitialData() {
      let historyListFailed = false;
      let activeSessionFailed = false;
      let unauthorized = false;
      function handleInitialError<T>(error: unknown, fallback: T, onFailure?: () => void): T {
        if (handleUnauthorizedError(error)) {
          unauthorized = true;
          return fallback;
        }
        onFailure?.();
        return fallback;
      }

      const [nextAppConfig, nextHistories, nextSession] = await Promise.all([
        getAppConfig().catch((error: unknown) => handleInitialError(error, {})),
        listChatHistories().catch((error: unknown) =>
          handleInitialError(error, [], () => {
            historyListFailed = true;
          }),
        ),
        getActiveChatSession().catch((error: unknown) =>
          handleInitialError(error, null, () => {
            activeSessionFailed = true;
          }),
        ),
      ]);
      if (!cancelled && isCurrentStream(initialStreamId) && !unauthorized) {
        setAppConfig(nextAppConfig);
        setHistories(nextHistories);
        setSession(nextSession);
        if (historyListFailed) {
          setSystemMessage(HISTORY_LIST_FAILED_MESSAGE);
        } else if (activeSessionFailed && nextHistories.length > 0) {
          setSystemMessage(HISTORY_DETAIL_FAILED_MESSAGE);
        } else {
          setSystemMessage(null);
        }
      }
    }

    void loadInitialData();

    return () => {
      cancelled = true;
    };
  }, [handleUnauthorizedError]);

  useEffect(() => {
    return () => {
      streamAbortControllerRef.current?.abort();
      streamAbortControllerRef.current = null;
      streamRunIdRef.current += 1;
    };
  }, []);

  function abortCurrentStream() {
    streamAbortControllerRef.current?.abort();
    streamAbortControllerRef.current = null;
  }

  function nextStreamRunId() {
    abortCurrentStream();
    streamRunIdRef.current += 1;
    return streamRunIdRef.current;
  }

  function isCurrentStream(runId: number) {
    return streamRunIdRef.current === runId;
  }

  function updateDisplayedRun(runId: string, update: (run: ChatRun) => ChatRun) {
    setSession((currentSession) => {
      /* istanbul ignore next -- SSE処理は表示中セッション確定後にだけ到達する */
      if (!currentSession) {
        return currentSession;
      }

      return {
        ...currentSession,
        runs: currentSession.runs.map((run) => (run.runId === runId ? update(run) : run)),
      };
    });
  }

  async function applySseEvent(event: SseEvent, streamId: number) {
    switch (event.event) {
      case "state":
        updateDisplayedRun(event.payload.run_id, (run) => ({
          ...run,
          state: event.payload.state,
        }));
        return;
      case "message":
        updateDisplayedRun(event.payload.run_id, (run) => ({
          ...run,
          intermediateMessages: [
            ...run.intermediateMessages,
            {
              id: `intermediate-${run.runId}-${run.intermediateMessages.length + 1}`,
              text: event.payload.text,
            },
          ],
        }));
        return;
      case "answer":
        setCancelingRunId((currentRunId) =>
          currentRunId === event.payload.run_id ? null : currentRunId,
        );
        updateDisplayedRun(event.payload.run_id, (run) => ({
          ...run,
          state: event.payload.state,
        }));
        await revealSubmittedAnswer({
          runId: event.payload.run_id,
          answer: {
            blocks: event.payload.answer.blocks.map((block) => ({
              markdown: block.markdown,
              references: block.references ?? [],
            })),
          },
          isCurrent: () => isCurrentStream(streamId),
          onThoughtComplete: () => closeThought(event.payload.run_id),
          onAnswerStart: startAnswer,
          onAnswerChange: updateAnswer,
          onAnswerComplete: completeAnswer,
        });
        return;
      case "error":
      case "canceled":
        if (
          event.event === "error" &&
          (event.payload.user_message === CHAT_DELETING_MESSAGE ||
            event.payload.user_message === CHAT_DELETED_MESSAGE)
        ) {
          moveToStart(event.payload.user_message);
          void refreshHistories();
          return;
        }
        setCancelingRunId((currentRunId) =>
          currentRunId === event.payload.run_id ? null : currentRunId,
        );
        updateDisplayedRun(event.payload.run_id, (run) => ({
          ...run,
          state: event.payload.state,
          statusMessage: event.payload.user_message,
        }));
    }
  }

  function startAnswer(runId: string, answer: ChatAnswer) {
    updateDisplayedRun(runId, (run) => ({
      ...run,
      answer,
    }));
  }

  function updateAnswer(runId: string, answer: ChatAnswer) {
    updateDisplayedRun(runId, (run) => ({
      ...run,
      answer,
    }));
  }

  function completeAnswer(runId: string, answer: ChatAnswer) {
    updateDisplayedRun(runId, (run) => ({
      ...run,
      answer,
    }));
  }

  async function refreshHistories() {
    try {
      setHistories(await listChatHistories());
    } catch (error) {
      if (handleUnauthorizedError(error)) {
        return;
      }
      setSystemMessage(HISTORY_LIST_FAILED_MESSAGE);
    }
  }

  async function streamAcceptedRun(
    response: { run_id: string; sse_url: string },
    streamId: number,
    displayedIntermediateMessageCount: number,
    chatId: string,
  ) {
    const streamController = new AbortController();
    streamAbortControllerRef.current = streamController;
    let replayedMessagesToSkip = displayedIntermediateMessageCount;
    try {
      await streamChatRun({
        sseUrl: response.sse_url,
        signal: streamController.signal,
        isCurrent: () => isCurrentStream(streamId),
        onEvent: async (event) => {
          if (event.event === "message" && replayedMessagesToSkip > 0) {
            replayedMessagesToSkip -= 1;
            return;
          }
          if (event.event === "state" && isTerminalRunState(event.payload.state)) {
            await refreshTerminalRunFromDetail(chatId, response.run_id, streamId);
            streamController.abort();
            return;
          }
          return applySseEvent(event, streamId);
        },
      });
    } catch {
      if (!isCurrentStream(streamId)) {
        return;
      }
      setCancelingRunId((currentRunId) => (currentRunId === response.run_id ? null : currentRunId));
      updateDisplayedRun(response.run_id, (run) => ({
        ...run,
        state: "error",
        statusMessage: SSE_DISCONNECTED_MESSAGE,
      }));
    } finally {
      if (streamAbortControllerRef.current === streamController) {
        streamAbortControllerRef.current = null;
      }
    }

    if (isCurrentStream(streamId)) {
      await refreshHistories();
    }
  }

  async function refreshTerminalRunFromDetail(chatId: string, runId: string, streamId: number) {
    try {
      const refreshedSession = await getChatDetail(chatId);
      if (!isCurrentStream(streamId)) {
        return;
      }
      setSession(refreshedSession);
      setCancelingRunId((currentRunId) => (currentRunId === runId ? null : currentRunId));
    } catch (error) {
      if (!isCurrentStream(streamId)) {
        return;
      }
      if (handleUnauthorizedError(error)) {
        return;
      }
      if (handleDeletedChatError(error)) {
        return;
      }
      setSystemMessage(HISTORY_DETAIL_FAILED_MESSAGE);
    }
  }

  function countDisplayedIntermediateMessages(targetSession: ChatSession, runId: string) {
    const targetRun = targetSession.runs.find((run) => run.runId === runId);
    return targetRun?.intermediateMessages.length ?? 0;
  }

  async function startSubmittedChat(message: string) {
    const streamId = nextStreamRunId();
    setPdfOpen(false);
    setReference(null);
    setOpenThoughtRunIds(new Set());
    setCancelingRunId(null);
    setScrollTargetRunId(undefined);
    setScrollReserveRunId(undefined);

    try {
      const accepted = await startChat(message);
      if (!isCurrentStream(streamId)) {
        return;
      }

      setSystemMessage(null);
      setSession(accepted.session);
      openThought(accepted.response.run_id);
      setMode("answer");
      window.scrollTo({ top: 0, behavior: "smooth" });
      await refreshHistories();
      await streamAcceptedRun(
        accepted.response,
        streamId,
        countDisplayedIntermediateMessages(accepted.session, accepted.response.run_id),
        accepted.response.chat_id,
      );
    } catch (error) {
      if (isCurrentStream(streamId)) {
        if (handleUnauthorizedError(error)) {
          return;
        }
        setSystemMessage(ACCEPTANCE_FAILED_MESSAGE);
        setMode("start");
      }
    }
  }

  async function submitContinuedInstruction(message: string) {
    /* istanbul ignore next -- 継続指示UIはセッション表示中にだけ描画される */
    if (!session) {
      return;
    }

    const streamId = nextStreamRunId();
    setPdfOpen(false);
    setReference(null);
    setCancelingRunId(null);
    setScrollTargetRunId(undefined);

    try {
      const accepted = await appendChatRun(session.id, message);
      if (!isCurrentStream(streamId)) {
        return;
      }

      setSystemMessage(null);
      setSession(accepted.session);
      openThought(accepted.response.run_id);
      setScrollReserveRunId(accepted.response.run_id);
      setScrollTargetRunId(accepted.response.run_id);
      await refreshHistories();
      await streamAcceptedRun(
        accepted.response,
        streamId,
        countDisplayedIntermediateMessages(accepted.session, accepted.response.run_id),
        accepted.response.chat_id,
      );
    } catch (error) {
      if (isCurrentStream(streamId)) {
        if (handleUnauthorizedError(error)) {
          return;
        }
        if (handleDeletedChatError(error)) {
          return;
        }
        setSystemMessage(ACCEPTANCE_FAILED_MESSAGE);
      }
    }
  }

  async function openHistorySession(chatId: string) {
    const streamId = nextStreamRunId();
    let nextSession: ChatSession;
    try {
      nextSession = await getChatDetail(chatId);
    } catch (error) {
      if (isCurrentStream(streamId)) {
        if (handleUnauthorizedError(error)) {
          return;
        }
        if (handleDeletedChatError(error)) {
          return;
        }
        setSystemMessage(HISTORY_DETAIL_FAILED_MESSAGE);
      }
      return;
    }
    if (!isCurrentStream(streamId)) {
      return;
    }

    setSystemMessage(null);
    setSession(nextSession);
    setPdfOpen(false);
    setReference(null);
    setCancelingRunId(null);
    setOpenThoughtRunIds(new Set());
    setScrollTargetRunId(undefined);
    setScrollReserveRunId(undefined);
    setMode("answer");

    const latestRun = nextSession.runs.at(-1);
    if (!latestRun || !isInProgressRun(latestRun.state)) {
      return;
    }

    openThought(latestRun.runId);
    await streamAcceptedRun(
      {
        run_id: latestRun.runId,
        sse_url: `/api/chats/${nextSession.id}/runs/${latestRun.runId}/sse`,
      },
      streamId,
      countDisplayedIntermediateMessages(nextSession, latestRun.runId),
      nextSession.id,
    );
  }

  function startNewChat() {
    moveToStart(null);
  }

  function moveToStart(message: string | null) {
    nextStreamRunId();
    setMode("start");
    setSystemMessage(message);
    setPdfOpen(false);
    setReference(null);
    setCancelingRunId(null);
    setOpenThoughtRunIds(new Set());
    setScrollTargetRunId(undefined);
    setScrollReserveRunId(undefined);
  }

  function openThought(runId: string) {
    setOpenThoughtRunIds((currentRunIds) => new Set([...currentRunIds, runId]));
  }

  function closeThought(runId: string) {
    setOpenThoughtRunIds((currentRunIds) => {
      const nextRunIds = new Set(currentRunIds);
      nextRunIds.delete(runId);
      return nextRunIds;
    });
  }

  function toggleThought(runId: string) {
    setOpenThoughtRunIds((currentRunIds) => {
      const nextRunIds = new Set(currentRunIds);
      if (nextRunIds.has(runId)) {
        nextRunIds.delete(runId);
      } else {
        nextRunIds.add(runId);
      }
      return nextRunIds;
    });
  }

  async function cancelDisplayedRun(runId: string) {
    /* istanbul ignore next -- キャンセルUIはセッション表示中にだけ描画される */
    if (!session) {
      return;
    }

    setCancelingRunId(runId);
    try {
      const response = await cancelChatRun(session.id, runId);
      updateDisplayedRun(response.run_id, (run) => ({
        ...run,
        state: response.state,
        statusMessage: response.user_message,
      }));
    } catch (error) {
      if (handleUnauthorizedError(error)) {
        return;
      }
      setCancelingRunId(null);
      updateDisplayedRun(runId, (run) => ({
        ...run,
        state: run.state === "cancel_requested" ? "running" : run.state,
        statusMessage: CANCEL_FAILED_MESSAGE,
      }));
    }
  }

  function openPdf(referenceToOpen: PdfReference) {
    setReference(referenceToOpen);
    setPdfOpen(true);
  }

  function requestDeleteCurrentChat() {
    if (!session?.id) {
      return;
    }
    setDeleteTarget({ chatId: session.id, title: session.title });
  }

  function requestDeleteHistoryChat(chatId: string) {
    const targetHistory = histories.find((history) => history.chatId === chatId);
    setDeleteTarget({ chatId, title: targetHistory?.title ?? "チャット" });
  }

  async function confirmDeleteChat() {
    if (!deleteTarget) {
      return;
    }
    const target = deleteTarget;
    const deletingCurrentChat = session?.id === target.chatId;
    setDeleteSubmitting(true);
    try {
      await deleteChat(target.chatId);
      setDeleteTarget(null);
      setHistories((currentHistories) =>
        currentHistories.filter((history) => history.chatId !== target.chatId),
      );
      if (deletingCurrentChat) {
        moveToStart(null);
      }
      await refreshHistories();
    } catch (error) {
      if (handleUnauthorizedError(error)) {
        return;
      }
      if (isDeletingOrDeletedError(error)) {
        setDeleteTarget(null);
        const message = statusOf(error) === 404 ? CHAT_DELETED_MESSAGE : CHAT_DELETING_MESSAGE;
        setHistories((currentHistories) =>
          currentHistories.filter((history) => history.chatId !== target.chatId),
        );
        if (deletingCurrentChat) {
          moveToStart(message);
        } else {
          setSystemMessage(message);
        }
        await refreshHistories();
      } else {
        setSystemMessage(CHAT_DELETE_FAILED_MESSAGE);
      }
    } finally {
      setDeleteSubmitting(false);
    }
  }

  function handleDeletedChatError(error: unknown) {
    if (!isDeletingOrDeletedError(error)) {
      return false;
    }
    moveToStart(statusOf(error) === 404 ? CHAT_DELETED_MESSAGE : CHAT_DELETING_MESSAGE);
    void refreshHistories();
    return true;
  }

  return (
    <>
      <AppShell
        activeChatId={mode === "answer" ? session?.id : undefined}
        currentUser={currentUser}
        histories={histories}
        onStartNewChat={startNewChat}
        onOpenAnswer={openHistorySession}
        onOpenAccountSettings={onOpenAccountSettings}
        onRequestDeleteCurrentChat={requestDeleteCurrentChat}
        onRequestDeleteHistoryChat={requestDeleteHistoryChat}
      >
        {({ sidebarCollapsed }) => (
          <>
            {systemMessage ? (
              <div
                className="absolute top-[76px] left-1/2 z-20 w-[min(720px,calc(100%-48px))] -translate-x-1/2 rounded-lg border border-[#f2b8b8] bg-[#fff6f6] px-4 py-3 text-sm font-[720] text-[#9f1d1d] shadow-[0_12px_30px_rgba(40,20,20,0.08)]"
                role="alert"
              >
                {systemMessage}
              </div>
            ) : null}
            {mode === "start" ? (
              <ChatStartScreen
                inputSuggestions={appConfig.input_suggestions ?? []}
                welcomeMessage={appConfig.welcome_message}
                onStart={startSubmittedChat}
              />
            ) : /* istanbul ignore next -- answerモードはセッション設定と同じ操作で切り替える */
            session ? (
              <ChatThread
                session={session}
                sidebarCollapsed={sidebarCollapsed}
                openThoughtRunIds={openThoughtRunIds}
                cancelingRunId={cancelingRunId}
                scrollReserveRunId={scrollReserveRunId}
                scrollTargetRunId={scrollTargetRunId}
                onToggleThought={toggleThought}
                onOpenPdf={openPdf}
                onCancelRun={cancelDisplayedRun}
                onScrollTargetHandled={() => setScrollTargetRunId(undefined)}
                onSubmitInstruction={submitContinuedInstruction}
              />
            ) : (
              <div className="p-8 text-sm text-[var(--dc-muted)]">チャットを読み込んでいます。</div>
            )}
          </>
        )}
      </AppShell>
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleteSubmitting) {
            setDeleteTarget(null);
          }
        }}
      >
        <DialogContent className="w-[min(420px,calc(100%-32px))] gap-5 p-6">
          <DialogHeader>
            <DialogTitle>チャットを削除しますか？</DialogTitle>
            <DialogDescription className="font-bold text-[var(--dc-danger)]">
              この操作は取り消せません。
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="ghost"
              disabled={deleteSubmitting}
              onClick={() => setDeleteTarget(null)}
            >
              キャンセル
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="disabled:opacity-60"
              disabled={deleteSubmitting}
              onClick={confirmDeleteChat}
            >
              OK
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <ReferenceViewerDialog open={pdfOpen} reference={reference} onOpenChange={setPdfOpen} />
    </>
  );
}

function isDeletingOrDeletedError(error: unknown) {
  const status = statusOf(error);
  return status === 404 || (status === 409 && messageOf(error) === CHAT_DELETING_MESSAGE);
}

function statusOf(error: unknown) {
  if (error === null || typeof error !== "object" || !("status" in error)) {
    return undefined;
  }
  const status = error.status;
  return typeof status === "number" ? status : undefined;
}

function messageOf(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return undefined;
}

function isInProgressRun(state: ChatRunState) {
  return (
    state === "accepted" ||
    state === "running" ||
    state === "validating" ||
    state === "cancel_requested"
  );
}

function isTerminalRunState(state: ChatRunState) {
  return (
    state === "completed" || state === "error" || state === "timed_out" || state === "canceled"
  );
}

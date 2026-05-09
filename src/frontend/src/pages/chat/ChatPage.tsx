import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import {
  appendChatRun,
  cancelChatRun,
  getActiveChatSession,
  getAppConfig,
  getChatDetail,
  listChatHistories,
  startChat,
  streamChatRun,
} from "@/features/chat/api/chatApi";
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

export function ChatPage() {
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
  const streamRunIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const initialStreamId = streamRunIdRef.current;

    async function loadInitialData() {
      let historyListFailed = false;
      let activeSessionFailed = false;
      const [nextAppConfig, nextHistories, nextSession] = await Promise.all([
        getAppConfig().catch(() => ({})),
        listChatHistories().catch(() => {
          historyListFailed = true;
          return [];
        }),
        getActiveChatSession().catch(() => {
          activeSessionFailed = true;
          return null;
        }),
      ]);
      if (!cancelled && isCurrentStream(initialStreamId)) {
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
  }, []);

  useEffect(() => {
    return () => {
      streamRunIdRef.current += 1;
    };
  }, []);

  function nextStreamRunId() {
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
    } catch {
      setSystemMessage(HISTORY_LIST_FAILED_MESSAGE);
    }
  }

  async function streamAcceptedRun(
    response: { run_id: string; sse_url: string },
    streamId: number,
    displayedIntermediateMessageCount: number,
  ) {
    let replayedMessagesToSkip = displayedIntermediateMessageCount;
    try {
      await streamChatRun({
        sseUrl: response.sse_url,
        isCurrent: () => isCurrentStream(streamId),
        onEvent: (event) => {
          if (event.event === "message" && replayedMessagesToSkip > 0) {
            replayedMessagesToSkip -= 1;
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
        state: "エラー",
        statusMessage: SSE_DISCONNECTED_MESSAGE,
      }));
    }

    if (isCurrentStream(streamId)) {
      await refreshHistories();
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
      );
    } catch {
      if (isCurrentStream(streamId)) {
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
      );
    } catch {
      if (isCurrentStream(streamId)) {
        setSystemMessage(ACCEPTANCE_FAILED_MESSAGE);
      }
    }
  }

  async function openHistorySession(chatId: string) {
    const streamId = nextStreamRunId();
    let nextSession: ChatSession;
    try {
      nextSession = await getChatDetail(chatId);
    } catch {
      if (isCurrentStream(streamId)) {
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
    );
  }

  function startNewChat() {
    nextStreamRunId();
    setMode("start");
    setSystemMessage(null);
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
    } catch {
      setCancelingRunId(null);
      updateDisplayedRun(runId, (run) => ({
        ...run,
        state: run.state === "キャンセル要求中" ? "実行中" : run.state,
        statusMessage: CANCEL_FAILED_MESSAGE,
      }));
    }
  }

  function openPdf(referenceToOpen: PdfReference) {
    setReference(referenceToOpen);
    setPdfOpen(true);
  }

  return (
    <>
      <AppShell
        activeChatId={mode === "answer" ? session?.id : undefined}
        histories={histories}
        onStartNewChat={startNewChat}
        onOpenAnswer={openHistorySession}
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
      <ReferenceViewerDialog open={pdfOpen} reference={reference} onOpenChange={setPdfOpen} />
    </>
  );
}

function isInProgressRun(state: ChatRunState) {
  return (
    state === "受付" || state === "実行中" || state === "検証中" || state === "キャンセル要求中"
  );
}

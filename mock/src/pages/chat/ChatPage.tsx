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
  ChatSession,
  SseEvent,
  ViewMode,
} from "@/features/chat/model/types";
import { ReferenceViewerDialog } from "@/features/reference-viewer/components/ReferenceViewerDialog";
import type { PdfReference } from "@/features/reference-viewer/model/types";

export function ChatPage() {
  const [mode, setMode] = useState<ViewMode>("start");
  const [appConfig, setAppConfig] = useState<AppConfigResponse>({});
  const [histories, setHistories] = useState<ChatHistoryItem[]>([]);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [reference, setReference] = useState<PdfReference | null>(null);
  const [openThoughtRunIds, setOpenThoughtRunIds] = useState<Set<string>>(() => new Set());
  const [pdfOpen, setPdfOpen] = useState(false);
  const [cancelingRunId, setCancelingRunId] = useState<string | null>(null);
  const [scrollTargetRunId, setScrollTargetRunId] = useState<string | undefined>();
  const [scrollReserveRunId, setScrollReserveRunId] = useState<string | undefined>();
  const streamRunIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function loadStubData() {
      const [nextAppConfig, nextHistories, nextSession] = await Promise.all([
        getAppConfig(),
        listChatHistories(),
        getActiveChatSession(),
      ]);
      if (!cancelled) {
        setAppConfig(nextAppConfig);
        setHistories(nextHistories);
        setSession(nextSession);
      }
    }

    void loadStubData();

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
        setCancelingRunId((currentRunId) => (currentRunId === event.payload.run_id ? null : currentRunId));
        updateDisplayedRun(event.payload.run_id, (run) => ({
          ...run,
          state: event.payload.state,
        }));
        await revealSubmittedAnswer({
          runId: event.payload.run_id,
          answer: {
            markdown: event.payload.answer.markdown,
            references: event.payload.answer.references ?? [],
          },
          isCurrent: () => isCurrentStream(streamId),
          onThoughtComplete: () => closeThought(event.payload.run_id),
          onAnswerStart: startAnswer,
          onAnswerMarkdown: updateAnswerMarkdown,
          onAnswerComplete: completeAnswer,
        });
        return;
      case "error":
      case "canceled":
        setCancelingRunId((currentRunId) => (currentRunId === event.payload.run_id ? null : currentRunId));
        updateDisplayedRun(event.payload.run_id, (run) => ({
          ...run,
          state: event.payload.state,
          statusMessage: event.payload.user_message,
        }));
    }
  }

  function startAnswer(runId: string) {
    updateDisplayedRun(runId, (run) => ({
      ...run,
      answer: {
        markdown: "",
        references: [],
      },
    }));
  }

  function updateAnswerMarkdown(runId: string, markdown: string) {
    updateDisplayedRun(runId, (run) => ({
      ...run,
      answer: {
        markdown,
        references: run.answer?.references ?? [],
      },
    }));
  }

  function completeAnswer(runId: string, answer: ChatAnswer) {
    updateDisplayedRun(runId, (run) => ({
      ...run,
      answer,
    }));
  }

  async function refreshHistories() {
    setHistories(await listChatHistories());
  }

  async function streamAcceptedRun(response: { run_id: string; sse_url: string }, streamId: number) {
    await streamChatRun({
      sseUrl: response.sse_url,
      isCurrent: () => isCurrentStream(streamId),
      onEvent: (event) => applySseEvent(event, streamId),
    });

    if (isCurrentStream(streamId)) {
      await refreshHistories();
    }
  }

  async function startSubmittedChat(message: string) {
    const streamId = nextStreamRunId();
    setPdfOpen(false);
    setReference(null);
    setOpenThoughtRunIds(new Set());
    setCancelingRunId(null);
    setScrollTargetRunId(undefined);
    setScrollReserveRunId(undefined);

    const accepted = await startChat(message);
    if (!isCurrentStream(streamId)) {
      return;
    }

    setSession(accepted.session);
    openThought(accepted.response.run_id);
    setMode("answer");
    window.scrollTo({ top: 0, behavior: "smooth" });
    await refreshHistories();
    await streamAcceptedRun(accepted.response, streamId);
  }

  async function submitContinuedInstruction(message: string) {
    if (!session) {
      return;
    }

    const streamId = nextStreamRunId();
    setPdfOpen(false);
    setReference(null);
    setCancelingRunId(null);
    setScrollTargetRunId(undefined);

    const accepted = await appendChatRun(session.id, message);
    if (!isCurrentStream(streamId)) {
      return;
    }

    setSession(accepted.session);
    openThought(accepted.response.run_id);
    setScrollReserveRunId(accepted.response.run_id);
    setScrollTargetRunId(accepted.response.run_id);
    await refreshHistories();
    await streamAcceptedRun(accepted.response, streamId);
  }

  async function openHistorySession(chatId: string) {
    nextStreamRunId();
    setSession(await getChatDetail(chatId));
    setPdfOpen(false);
    setReference(null);
    setCancelingRunId(null);
    setOpenThoughtRunIds(new Set());
    setScrollTargetRunId(undefined);
    setScrollReserveRunId(undefined);
    setMode("answer");
  }

  function startNewChat() {
    nextStreamRunId();
    setMode("start");
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
      setCancelingRunId((currentRunId) => (currentRunId === runId ? null : currentRunId));
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
        {({ sidebarCollapsed }) =>
          mode === "start" ? (
            <ChatStartScreen
              inputSuggestions={appConfig.input_suggestions ?? []}
              welcomeMessage={appConfig.welcome_message}
              onStart={startSubmittedChat}
            />
          ) : session ? (
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
          )
        }
      </AppShell>
      <ReferenceViewerDialog open={pdfOpen} reference={reference} onOpenChange={setPdfOpen} />
    </>
  );
}

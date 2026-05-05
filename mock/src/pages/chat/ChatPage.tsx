import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { getActiveChatSession, listChatHistories, submitChatMessage } from "@/features/chat/api/chatApi";
import { ChatStartScreen } from "@/features/chat/components/ChatStartScreen";
import { ChatThread } from "@/features/chat/components/ChatThread";
import { revealSubmittedSession } from "@/features/chat/lib/revealAnswer";
import type { ChatAnswerBlock, ChatHistoryItem, ChatSession, ThoughtStep, ViewMode } from "@/features/chat/model/types";
import { ReferenceViewerDialog } from "@/features/reference-viewer/components/ReferenceViewerDialog";
import type { PdfReference } from "@/features/reference-viewer/model/types";

export function ChatPage() {
  const [mode, setMode] = useState<ViewMode>("start");
  const [histories, setHistories] = useState<ChatHistoryItem[]>([]);
  const [historySession, setHistorySession] = useState<ChatSession | null>(null);
  const [completedSession, setCompletedSession] = useState<ChatSession | null>(null);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [reference, setReference] = useState<PdfReference | null>(null);
  const [thoughtOpen, setThoughtOpen] = useState(true);
  const [pdfOpen, setPdfOpen] = useState(false);
  const revealRunIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function loadStubData() {
      const [nextHistories, nextSession] = await Promise.all([
        listChatHistories(),
        getActiveChatSession(),
      ]);
      if (!cancelled) {
        setHistories(nextHistories);
        setHistorySession(nextSession);
        setCompletedSession(nextSession);
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
      revealRunIdRef.current += 1;
    };
  }, []);

  function nextRevealRunId() {
    revealRunIdRef.current += 1;
    return revealRunIdRef.current;
  }

  function isCurrentRevealRun(runId: number) {
    return revealRunIdRef.current === runId;
  }

  function updateDisplayedSession(update: (current: ChatSession) => ChatSession) {
    setSession((current) => (current ? update(current) : current));
  }

  function appendThoughtStep(step: ThoughtStep) {
    updateDisplayedSession((current) => ({
      ...current,
      thoughtSteps: [...current.thoughtSteps, step],
    }));
  }

  function startAnswerBlock(block: ChatAnswerBlock) {
    updateDisplayedSession((current) => ({
      ...current,
      answer: {
        blocks: [
          ...current.answer.blocks,
          {
            ...block,
            markdown: "",
            references: [],
          },
        ],
      },
    }));
  }

  function updateAnswerBlockMarkdown(blockId: string, markdown: string) {
    updateDisplayedSession((current) => ({
      ...current,
      answer: {
        blocks: current.answer.blocks.map((block) => (block.id === blockId ? { ...block, markdown } : block)),
      },
    }));
  }

  function completeAnswerBlock(blockToComplete: ChatAnswerBlock) {
    updateDisplayedSession((current) => ({
      ...current,
      answer: {
        blocks: current.answer.blocks.map((block) => (block.id === blockToComplete.id ? blockToComplete : block)),
      },
    }));
  }

  async function startSubmittedChat(message: string) {
    const runId = nextRevealRunId();
    setPdfOpen(false);
    setReference(null);
    setThoughtOpen(true);
    setSession(createPendingSession(message));
    setMode("answer");

    const nextCompletedSession = await submitChatMessage(message);

    if (!isCurrentRevealRun(runId)) {
      return;
    }

    setCompletedSession(nextCompletedSession);

    await revealSubmittedSession({
      completedSession: nextCompletedSession,
      isCurrent: () => isCurrentRevealRun(runId),
      onThoughtStep: appendThoughtStep,
      onThoughtComplete: () => setThoughtOpen(false),
      onAnswerBlockStart: startAnswerBlock,
      onAnswerBlockMarkdown: updateAnswerBlockMarkdown,
      onAnswerBlockComplete: completeAnswerBlock,
    });
  }

  function openHistorySession() {
    nextRevealRunId();
    if (historySession) {
      setSession(historySession);
    }
    setPdfOpen(false);
    setReference(null);
    setThoughtOpen(false);
    setMode("answer");
  }

  function startNewChat() {
    nextRevealRunId();
    setMode("start");
    setPdfOpen(false);
    setReference(null);
    setThoughtOpen(true);
  }

  function openPdf(referenceToOpen: PdfReference) {
    setReference(referenceToOpen);
    setPdfOpen(true);
  }

  return (
    <>
      <AppShell histories={histories} onStartNewChat={startNewChat} onOpenAnswer={openHistorySession}>
        {({ sidebarCollapsed }) =>
          mode === "start" ? (
            <ChatStartScreen onStart={startSubmittedChat} />
          ) : session ? (
            <ChatThread
              session={session}
              sidebarCollapsed={sidebarCollapsed}
              thoughtOpen={thoughtOpen}
              onToggleThought={() => setThoughtOpen((current) => !current)}
              onOpenPdf={openPdf}
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

function createPendingSession(message: string): ChatSession {
  return {
    id: `submitted-${Date.now()}`,
    userMessage: {
      id: `message-user-${Date.now()}`,
      role: "user",
      text: message,
    },
    thoughtSteps: [],
    answer: {
      blocks: [],
    },
  };
}

import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { getActiveChatSession, getPdfReference, listChatHistories } from "@/features/chat/api/chatApi";
import { ChatStartScreen } from "@/features/chat/components/ChatStartScreen";
import { ChatThread } from "@/features/chat/components/ChatThread";
import type { ChatHistoryItem, ChatSession, ViewMode } from "@/features/chat/model/types";
import { ReferenceViewerDialog } from "@/features/reference-viewer/components/ReferenceViewerDialog";
import type { PdfReference } from "@/features/reference-viewer/model/types";

export function ChatPage() {
  const [mode, setMode] = useState<ViewMode>("start");
  const [histories, setHistories] = useState<ChatHistoryItem[]>([]);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [reference, setReference] = useState<PdfReference | null>(null);
  const [thoughtOpen, setThoughtOpen] = useState(true);
  const [pdfOpen, setPdfOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadStubData() {
      const [nextHistories, nextSession, nextReference] = await Promise.all([
        listChatHistories(),
        getActiveChatSession(),
        getPdfReference(),
      ]);
      if (!cancelled) {
        setHistories(nextHistories);
        setSession(nextSession);
        setReference(nextReference);
      }
    }

    void loadStubData();

    return () => {
      cancelled = true;
    };
  }, []);

  function openAnswer() {
    setMode("answer");
  }

  return (
    <>
      <AppShell histories={histories} onOpenAnswer={openAnswer}>
        {mode === "start" ? (
          <ChatStartScreen onStart={openAnswer} />
        ) : session ? (
          <ChatThread
            session={session}
            thoughtOpen={thoughtOpen}
            onToggleThought={() => setThoughtOpen((current) => !current)}
            onOpenPdf={() => setPdfOpen(true)}
          />
        ) : (
          <div className="p-8 text-sm text-[#65728c]">チャットを読み込んでいます。</div>
        )}
      </AppShell>
      <ReferenceViewerDialog open={pdfOpen} reference={reference} onOpenChange={setPdfOpen} />
    </>
  );
}

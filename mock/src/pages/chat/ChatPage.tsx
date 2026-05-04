import { useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { ChatStartScreen } from "@/features/chat/components/ChatStartScreen";
import { ChatThread } from "@/features/chat/components/ChatThread";
import type { ViewMode } from "@/features/chat/model/types";
import { ReferenceViewerDialog } from "@/features/reference-viewer/components/ReferenceViewerDialog";

export function ChatPage() {
  const [mode, setMode] = useState<ViewMode>("start");
  const [thoughtOpen, setThoughtOpen] = useState(true);
  const [pdfOpen, setPdfOpen] = useState(false);

  function openAnswer() {
    setMode("answer");
  }

  return (
    <>
      <AppShell onOpenAnswer={openAnswer}>
        {mode === "start" ? (
          <ChatStartScreen onStart={openAnswer} />
        ) : (
          <ChatThread
            thoughtOpen={thoughtOpen}
            onToggleThought={() => setThoughtOpen((current) => !current)}
            onOpenPdf={() => setPdfOpen(true)}
          />
        )}
      </AppShell>
      <ReferenceViewerDialog open={pdfOpen} onOpenChange={setPdfOpen} />
    </>
  );
}

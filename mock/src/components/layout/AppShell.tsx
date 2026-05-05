import type { ReactNode } from "react";

import type { ChatHistoryItem } from "@/features/chat/model/types";
import { Sidebar } from "./Sidebar";
import { TopMenu } from "./TopMenu";

export function AppShell({
  children,
  histories,
  onOpenAnswer,
}: {
  children: ReactNode;
  histories: ChatHistoryItem[];
  onOpenAnswer: () => void;
}) {
  return (
    <div className="grid min-h-screen grid-cols-[350px_minmax(0,1fr)] text-[#111827] max-[1280px]:grid-cols-[320px_minmax(0,1fr)]">
      <Sidebar histories={histories} onOpenAnswer={onOpenAnswer} />
      <main className="relative min-h-screen min-w-0 overflow-hidden bg-white">
        <TopMenu />
        {children}
      </main>
    </div>
  );
}

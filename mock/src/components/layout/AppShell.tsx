import { useState } from "react";
import type { ReactNode } from "react";

import type { ChatHistoryItem } from "@/features/chat/model/types";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";
import { TopMenu } from "./TopMenu";

type AppShellRenderState = {
  sidebarCollapsed: boolean;
};

export function AppShell({
  children,
  histories,
  onOpenAnswer,
}: {
  children: ReactNode | ((state: AppShellRenderState) => ReactNode);
  histories: ChatHistoryItem[];
  onOpenAnswer: () => void;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div
      className={cn(
        "grid min-h-screen text-[#111827] transition-[grid-template-columns] duration-200 ease-out",
        sidebarCollapsed
          ? "grid-cols-[72px_minmax(0,1fr)]"
          : "grid-cols-[350px_minmax(0,1fr)] max-[1280px]:grid-cols-[320px_minmax(0,1fr)]",
      )}
    >
      <Sidebar
        collapsed={sidebarCollapsed}
        histories={histories}
        onOpenAnswer={onOpenAnswer}
        onToggleCollapsed={() => setSidebarCollapsed((current) => !current)}
      />
      <main className="relative min-h-screen min-w-0 overflow-hidden bg-white">
        <TopMenu />
        {typeof children === "function" ? children({ sidebarCollapsed }) : children}
      </main>
    </div>
  );
}

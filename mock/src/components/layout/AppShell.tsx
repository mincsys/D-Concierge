import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { ChatHistoryItem } from "@/features/chat/model/types";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";
import { TopMenu } from "./TopMenu";

type AppShellRenderState = {
  sidebarCollapsed: boolean;
};

const AUTO_COLLAPSE_WIDTH = 1100;

export function AppShell({
  children,
  histories,
  onStartNewChat,
  onOpenAnswer,
}: {
  children: ReactNode | ((state: AppShellRenderState) => ReactNode);
  histories: ChatHistoryItem[];
  onStartNewChat: () => void;
  onOpenAnswer: () => void;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const autoCollapsedRef = useRef(false);
  const wasNarrowRef = useRef(false);

  useEffect(() => {
    function syncSidebarWithWindowWidth() {
      const narrow = window.innerWidth <= AUTO_COLLAPSE_WIDTH;

      if (narrow && !wasNarrowRef.current) {
        setSidebarCollapsed(true);
        autoCollapsedRef.current = true;
      }

      if (!narrow && autoCollapsedRef.current) {
        setSidebarCollapsed(false);
        autoCollapsedRef.current = false;
      }

      wasNarrowRef.current = narrow;
    }

    syncSidebarWithWindowWidth();
    window.addEventListener("resize", syncSidebarWithWindowWidth);

    return () => {
      window.removeEventListener("resize", syncSidebarWithWindowWidth);
    };
  }, []);

  function handleToggleCollapsed() {
    autoCollapsedRef.current = false;
    setSidebarCollapsed((current) => !current);
  }

  return (
    <div
      className={cn(
        "grid min-h-screen text-[var(--dc-text-strong)] transition-[grid-template-columns] duration-200 ease-out",
        sidebarCollapsed
          ? "grid-cols-[64px_minmax(0,1fr)]"
          : "grid-cols-[320px_minmax(0,1fr)]",
      )}
    >
      <Sidebar
        collapsed={sidebarCollapsed}
        histories={histories}
        onStartNewChat={onStartNewChat}
        onOpenAnswer={onOpenAnswer}
        onToggleCollapsed={handleToggleCollapsed}
      />
      <main className="relative min-h-screen min-w-0 overflow-hidden bg-[var(--dc-app-bg)]">
        <TopMenu />
        {typeof children === "function" ? children({ sidebarCollapsed }) : children}
      </main>
    </div>
  );
}

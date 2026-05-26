import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { ChatHistoryItem } from "@/features/chat/model/types";
import type { AccountUser } from "@/features/account/model/types";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";
import { TopMenu } from "./TopMenu";

type AppShellRenderState = {
  sidebarCollapsed: boolean;
};

const AUTO_COLLAPSE_WIDTH = 1100;

export function AppShell({
  activeChatId,
  children,
  currentUser,
  histories,
  onStartNewChat,
  onOpenAnswer,
  onOpenAccountSettings,
  onRequestDeleteCurrentChat,
  onRequestDeleteHistoryChat,
}: {
  activeChatId?: string;
  children: ReactNode | ((state: AppShellRenderState) => ReactNode);
  currentUser: AccountUser;
  histories: ChatHistoryItem[];
  onStartNewChat: () => void;
  onOpenAnswer: (chatId: string) => void;
  onOpenAccountSettings?: () => void;
  onRequestDeleteCurrentChat?: () => void;
  onRequestDeleteHistoryChat?: (chatId: string) => void;
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
        sidebarCollapsed ? "grid-cols-[64px_minmax(0,1fr)]" : "grid-cols-[320px_minmax(0,1fr)]",
      )}
    >
      <Sidebar
        activeChatId={activeChatId}
        collapsed={sidebarCollapsed}
        currentUser={currentUser}
        histories={histories}
        onStartNewChat={onStartNewChat}
        onOpenAnswer={onOpenAnswer}
        onOpenAccountSettings={onOpenAccountSettings}
        onRequestDeleteHistoryChat={onRequestDeleteHistoryChat}
        onToggleCollapsed={handleToggleCollapsed}
      />
      <main className="relative min-h-screen min-w-0 overflow-hidden bg-[var(--dc-app-bg)]">
        {activeChatId ? (
          <TopMenu deleteDisabled={false} onRequestDelete={onRequestDeleteCurrentChat} />
        ) : null}
        {typeof children === "function" ? children({ sidebarCollapsed }) : children}
      </main>
    </div>
  );
}

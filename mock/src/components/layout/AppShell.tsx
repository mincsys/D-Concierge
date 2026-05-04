import type { ReactNode } from "react";

import { Sidebar } from "./Sidebar";
import { TopMenu } from "./TopMenu";

export function AppShell({
  children,
  onOpenAnswer,
}: {
  children: ReactNode;
  onOpenAnswer: () => void;
}) {
  return (
    <div className="grid min-h-screen grid-cols-[350px_1fr] text-[#111827] max-[1280px]:grid-cols-[320px_1fr]">
      <Sidebar onOpenAnswer={onOpenAnswer} />
      <main className="relative min-h-screen bg-white">
        <TopMenu />
        {children}
      </main>
    </div>
  );
}

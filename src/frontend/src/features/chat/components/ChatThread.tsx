import { useLayoutEffect, useRef } from "react";

import { AnswerContent } from "@/features/answer-rendering/components/AnswerContent";
import type { ChatSession } from "@/features/chat/model/types";
import type { PdfReference } from "@/features/reference-viewer/model/types";
import { cn } from "@/lib/utils";
import { ChatComposer } from "./ChatComposer";
import { ThoughtPanel } from "./ThoughtPanel";

const CONTINUED_RUN_SCROLL_OFFSET_RATIO = 0.2;
const CONTINUED_RUN_SCROLL_RESERVE_CLASS = "min-h-[80vh]";

export function ChatThread({
  cancelingRunId,
  openThoughtRunIds,
  scrollReserveRunId,
  scrollTargetRunId,
  session,
  sidebarCollapsed,
  onToggleThought,
  onOpenPdf,
  onCancelRun,
  onScrollTargetHandled,
  onSubmitInstruction,
}: {
  cancelingRunId?: string | null;
  openThoughtRunIds: Set<string>;
  scrollReserveRunId?: string;
  scrollTargetRunId?: string;
  session: ChatSession;
  sidebarCollapsed: boolean;
  onToggleThought: (runId: string) => void;
  onOpenPdf: (reference: PdfReference) => void;
  onCancelRun: (runId: string) => void;
  onScrollTargetHandled: () => void;
  onSubmitInstruction: (message: string) => void;
}) {
  const scrollTargetElementRef = useRef<HTMLDivElement | null>(null);
  const latestRun = session.runs.at(-1);
  const composerActionMode =
    latestRun && (cancelingRunId === latestRun.runId || latestRun.state === "cancel_requested")
      ? "canceling"
      : latestRun &&
          (latestRun.state === "accepted" ||
            latestRun.state === "running" ||
            latestRun.state === "validating")
        ? "cancel"
        : "send";

  useLayoutEffect(() => {
    if (!scrollTargetRunId) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      const targetElement = scrollTargetElementRef.current;
      /* istanbul ignore next -- スクロール対象runがある場合はref設定済みの要素へ到達する */
      if (!targetElement) {
        return;
      }

      const targetTop = targetElement.getBoundingClientRect().top + window.scrollY;
      const scrollTop = Math.max(
        0,
        targetTop - window.innerHeight * CONTINUED_RUN_SCROLL_OFFSET_RATIO,
      );
      window.scrollTo({ top: scrollTop, behavior: "smooth" });
      onScrollTargetHandled();
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [onScrollTargetHandled, scrollTargetRunId, session.runs]);

  return (
    <section className="min-h-screen px-[34px] pt-[60px] pb-[110px] max-[1024px]:px-5">
      <div
        className={cn(
          "mx-auto w-full transition-[max-width] duration-200 ease-out",
          sidebarCollapsed ? "max-w-[1260px]" : "max-w-none max-[1100px]:max-w-[640px]",
        )}
      >
        {session.runs.map((run) => (
          <div
            ref={run.runId === scrollTargetRunId ? scrollTargetElementRef : undefined}
            className={cn(
              "mt-9 first:mt-0",
              run.runId === scrollReserveRunId && CONTINUED_RUN_SCROLL_RESERVE_CLASS,
            )}
            key={run.runId}
          >
            <div className="ml-auto mr-3 w-fit max-w-[470px] whitespace-pre-wrap rounded-2xl bg-[var(--dc-user-bubble)] px-[26px] py-5 text-[15.5px] font-normal text-[var(--dc-text)]">
              {run.userInstruction}
            </div>
            <article
              className={cn(
                "grid w-[min(820px,100%)] gap-[25px]",
                sidebarCollapsed
                  ? "mt-0"
                  : "ml-7 max-[1280px]:w-[min(760px,100%)] max-[1100px]:ml-0",
              )}
            >
              <ThoughtPanel
                busy={isInProgressRun(run.state)}
                open={openThoughtRunIds.has(run.runId)}
                messages={run.intermediateMessages}
                onToggle={() => onToggleThought(run.runId)}
              />
              {run.answer ? <AnswerContent answer={run.answer} onOpenPdf={onOpenPdf} /> : null}
              {run.statusMessage ? (
                <div className="ml-20 mt-5 rounded-lg border border-[var(--dc-border-soft)] bg-white px-4 py-3 text-sm font-[650] text-[var(--dc-muted-strong)] max-[1100px]:ml-0">
                  {run.statusMessage}
                </div>
              ) : null}
            </article>
          </div>
        ))}
      </div>
      <div
        className={cn(
          "fixed right-[35px] bottom-4 flex justify-center transition-[right,left] duration-200 ease-out max-[1100px]:right-14",
          sidebarCollapsed ? "left-[99px]" : "left-[355px]",
        )}
      >
        <ChatComposer
          actionMode={composerActionMode}
          autoFocus
          className="w-full max-w-[1040px]"
          onCancel={latestRun ? () => onCancelRun(latestRun.runId) : undefined}
          onSubmit={onSubmitInstruction}
        />
      </div>
    </section>
  );
}

function isInProgressRun(state: ChatSession["runs"][number]["state"]) {
  return (
    state === "accepted" ||
    state === "running" ||
    state === "validating" ||
    state === "cancel_requested"
  );
}

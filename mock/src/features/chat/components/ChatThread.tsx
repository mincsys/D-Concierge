import { AnswerContent } from "@/features/answer-rendering/components/AnswerContent";
import type { ChatSession } from "@/features/chat/model/types";
import type { PdfReference } from "@/features/reference-viewer/model/types";
import { cn } from "@/lib/utils";
import { ChatComposer } from "./ChatComposer";
import { ThoughtPanel } from "./ThoughtPanel";

export function ChatThread({
  session,
  sidebarCollapsed,
  thoughtOpen,
  onToggleThought,
  onOpenPdf,
}: {
  session: ChatSession;
  sidebarCollapsed: boolean;
  thoughtOpen: boolean;
  onToggleThought: () => void;
  onOpenPdf: (reference: PdfReference) => void;
}) {
  return (
    <section className="min-h-screen px-[34px] pt-[60px] pb-[110px] max-[1024px]:px-5">
      <div
        className={cn(
          "mx-auto w-full transition-[max-width] duration-200 ease-out",
          sidebarCollapsed ? "max-w-[1260px]" : "max-w-none max-[1100px]:max-w-[640px]",
        )}
      >
        <div className="ml-auto mr-3 w-fit max-w-[470px] rounded-2xl bg-[#dceaff] px-[26px] py-5 text-[15.5px] font-[760] text-[#132036]">
          {session.userMessage.text}
        </div>
        <article
          className={cn(
            "w-[min(820px,100%)]",
            sidebarCollapsed ? "mt-0" : "ml-7 max-[1280px]:w-[min(760px,100%)] max-[1100px]:ml-0",
          )}
        >
          <ThoughtPanel open={thoughtOpen} steps={session.thoughtSteps} onToggle={onToggleThought} />
          <AnswerContent answer={session.answer} onOpenPdf={onOpenPdf} />
        </article>
      </div>
      <div
        className={cn(
          "fixed right-[35px] bottom-4 transition-[right,left] duration-200 ease-out max-[1100px]:right-14",
          sidebarCollapsed ? "left-[99px]" : "left-[355px]",
        )}
      >
        <ChatComposer placeholder={session.composerPlaceholder} onSubmit={() => undefined} />
      </div>
    </section>
  );
}

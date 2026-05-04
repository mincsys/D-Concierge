import { AnswerContent } from "@/features/answer-rendering/components/AnswerContent";
import type { ChatSession } from "@/features/chat/model/types";
import { ChatComposer } from "./ChatComposer";
import { ThoughtPanel } from "./ThoughtPanel";

export function ChatThread({
  session,
  thoughtOpen,
  onToggleThought,
  onOpenPdf,
}: {
  session: ChatSession;
  thoughtOpen: boolean;
  onToggleThought: () => void;
  onOpenPdf: () => void;
}) {
  return (
    <section className="min-h-screen px-[34px] pt-[60px] pb-[110px]">
      <div className="ml-auto mr-3 w-fit max-w-[470px] rounded-2xl bg-[#dceaff] px-[26px] py-5 text-[15.5px] font-[760] text-[#132036]">
        {session.userMessage.text}
      </div>
      <article className="ml-7 w-[min(820px,calc(100vw-500px))] max-[1280px]:w-[min(760px,calc(100vw-420px))]">
        <ThoughtPanel open={thoughtOpen} steps={session.thoughtSteps} onToggle={onToggleThought} />
        <AnswerContent answer={session.answer} onOpenPdf={onOpenPdf} />
      </article>
      <div className="fixed right-[35px] bottom-4 left-[385px] max-[1280px]:left-[355px]">
        <ChatComposer placeholder={session.composerPlaceholder} onSubmit={() => undefined} />
      </div>
    </section>
  );
}

import { ChevronDown, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { IntermediateMessage } from "@/features/chat/model/types";
import { cn } from "@/lib/utils";

export function ThoughtPanel({
  open,
  messages,
  onToggle,
}: {
  open: boolean;
  messages: IntermediateMessage[];
  onToggle: () => void;
}) {
  return (
    <div>
      <Button
        className="inline-flex h-[45px] items-center gap-[11px] bg-transparent p-0 text-[21px] font-[760] text-[#4f5f78] shadow-none hover:bg-transparent hover:text-[#4f5f78]"
        type="button"
        variant="ghost"
        onClick={onToggle}
      >
        <span className="grid size-10 place-items-center rounded-full bg-[var(--dc-primary)] text-white shadow-[0_8px_18px_var(--dc-shadow-primary)]">
          <Sparkles size={22} fill="currentColor" />
        </span>
        <ChevronDown
          className={cn("text-[var(--dc-muted)] transition-transform duration-150", open ? "rotate-0" : "-rotate-90")}
          size={19}
        />
        <span>作業プロセス</span>
      </Button>
      {open ? (
        <div className="mt-[11px] mb-[25px] ml-[60px] border-l-2 border-[#aab5c8] pl-[22px] text-base leading-[1.9] font-normal text-[#4f5f78] max-[1100px]:ml-[60px]">
          {messages.map((message) => (
            <div key={message.id}>{message.text}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

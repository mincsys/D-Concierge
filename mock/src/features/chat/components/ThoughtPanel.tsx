import { ChevronDown, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { thoughtLines } from "@/features/chat/model/fixtures";
import { cn } from "@/lib/utils";

export function ThoughtPanel({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div>
      <Button
        className="inline-flex h-[45px] items-center gap-[11px] bg-transparent p-0 text-[21px] font-[760] text-[#111827] shadow-none hover:bg-transparent hover:text-[#111827]"
        type="button"
        variant="ghost"
        onClick={onToggle}
      >
        <span className="grid size-10 place-items-center rounded-full bg-[#f1f6ff] text-[#0d64ff] shadow-[inset_0_0_0_1px_#dfebff]">
          <Sparkles size={22} fill="#0d64ff" />
        </span>
        <ChevronDown
          className={cn("text-[#65728c] transition-transform duration-150", open ? "rotate-0" : "-rotate-90")}
          size={19}
        />
        <span>Thought for 16s</span>
      </Button>
      {open ? (
        <div className="mt-[11px] mb-[25px] ml-20 border-l-2 border-[#aab5c8] pl-[22px] text-base leading-[1.9] font-[690] text-[#16233a]">
          {thoughtLines.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

import { Button } from "@/components/ui/button";
import type { ChatHistoryItem } from "@/features/chat/model/types";
import { cn } from "@/lib/utils";

export function ChatHistoryList({
  histories,
  onOpenAnswer,
}: {
  histories: ChatHistoryItem[];
  onOpenAnswer: () => void;
}) {
  return (
    <nav className="flex flex-col gap-2 pr-0" aria-label="最近のチャット">
      {histories.map((item, index) => (
        <Button
          className={cn(
            "relative min-h-9 w-full justify-start overflow-hidden rounded-[7px] bg-transparent px-[13px] text-left text-[15.5px] font-[620] text-ellipsis whitespace-nowrap text-[#111827] shadow-none hover:bg-[#eef6ff]",
            index === 0 &&
              "bg-linear-to-r from-[#eef6ff] to-[#e8f2fd] before:absolute before:top-0 before:bottom-0 before:left-0 before:w-1 before:rounded before:bg-[#0a64ff]",
          )}
          key={item.id}
          type="button"
          variant="ghost"
          onClick={onOpenAnswer}
        >
          {item.title}
        </Button>
      ))}
    </nav>
  );
}

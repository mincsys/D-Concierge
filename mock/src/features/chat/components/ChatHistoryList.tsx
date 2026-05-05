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
    <nav className="flex flex-col pr-0" aria-label="最近のチャット">
      {histories.map((item, index) => (
        <Button
          className={cn(
            "relative min-h-[46px] w-full justify-start overflow-hidden rounded-none bg-transparent px-8 text-left text-[15.5px] font-[620] text-ellipsis whitespace-nowrap text-[var(--dc-text-strong)] shadow-none hover:bg-[var(--dc-primary-hover)]",
            index === 0 &&
              "min-h-[56px] border-y border-l-[5px] border-y-[var(--dc-border-soft)] border-l-[var(--dc-primary)] bg-transparent pl-[27px] text-[var(--dc-primary)] hover:bg-transparent",
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

import { Button } from "@/components/ui/button";
import type { ChatHistoryItem } from "@/features/chat/model/types";
import { cn } from "@/lib/utils";

export function ChatHistoryList({
  activeChatId,
  histories,
  onOpenAnswer,
}: {
  activeChatId?: string;
  histories: ChatHistoryItem[];
  onOpenAnswer: (chatId: string) => void;
}) {
  return (
    <nav className="flex flex-col pr-0" aria-label="最近のチャット">
      {histories.map((item) => (
        <Button
          className={cn(
            "relative min-h-[46px] w-full justify-start overflow-hidden rounded-none border-y border-l-[5px] border-y-transparent border-l-transparent bg-transparent pr-8 pl-[27px] text-left text-[15.5px] font-[620] text-ellipsis whitespace-nowrap text-[var(--dc-text-strong)] shadow-none hover:bg-[var(--dc-primary-hover)]",
            item.chatId === activeChatId &&
              "border-y-[var(--dc-border-soft)] border-l-[var(--dc-primary)] bg-transparent text-[var(--dc-primary)] hover:bg-transparent hover:text-[var(--dc-primary)]",
          )}
          key={item.chatId}
          type="button"
          variant="ghost"
          onClick={() => onOpenAnswer(item.chatId)}
        >
          {item.title}
        </Button>
      ))}
    </nav>
  );
}

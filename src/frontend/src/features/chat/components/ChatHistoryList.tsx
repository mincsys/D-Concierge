import { MoreHorizontal, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { ActionMenuPopover } from "@/components/action-menu/ActionMenuPopover";
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
  const [openMenuChatId, setOpenMenuChatId] = useState<string | null>(null);

  return (
    <nav className="flex flex-col pr-0" aria-label="最近のチャット">
      {histories.map((item) => (
        <ChatHistoryListItem
          active={item.chatId === activeChatId}
          key={item.chatId}
          item={item}
          menuOpen={openMenuChatId === item.chatId}
          onMenuOpenChange={(open) => setOpenMenuChatId(open ? item.chatId : null)}
          onOpenAnswer={onOpenAnswer}
        />
      ))}
    </nav>
  );
}

function ChatHistoryListItem({
  active,
  item,
  menuOpen,
  onMenuOpenChange,
  onOpenAnswer,
}: {
  active: boolean;
  item: ChatHistoryItem;
  menuOpen: boolean;
  onMenuOpenChange: (open: boolean) => void;
  onOpenAnswer: (chatId: string) => void;
}) {
  const menuRootRef = useRef<HTMLDivElement | null>(null);

  return (
    <div className="group relative" ref={menuRootRef}>
      <Button
        className={cn(
          "relative min-h-[46px] w-full min-w-0 justify-start overflow-hidden rounded-none border-y border-l-[5px] border-y-transparent border-l-transparent bg-transparent pr-8 pl-[27px] text-left text-[15.5px] font-[620] text-[var(--dc-text-strong)] shadow-none hover:bg-[var(--dc-primary-hover)] group-hover:pr-12 group-focus-within:pr-12",
          active &&
            "border-y-[var(--dc-border-soft)] border-l-[var(--dc-primary)] bg-transparent text-[var(--dc-primary)] hover:bg-transparent hover:text-[var(--dc-primary)]",
        )}
        title={item.title}
        type="button"
        variant="ghost"
        onClick={() => onOpenAnswer(item.chatId)}
      >
        <span className="block min-w-0 truncate">{item.title}</span>
      </Button>
      <Button
        className="absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:bg-[var(--dc-primary-softer)] hover:text-[var(--dc-primary-strong)]"
        type="button"
        variant="ghost"
        aria-expanded={menuOpen}
        aria-haspopup="menu"
        aria-label={`${item.title}のメニュー`}
        onClick={(event) => {
          event.stopPropagation();
          onMenuOpenChange(!menuOpen);
        }}
      >
        <MoreHorizontal size={22} />
      </Button>
      <ActionMenuPopover
        open={menuOpen}
        ariaLabel="履歴項目メニュー"
        className="top-[38px] right-2 z-10"
        dismissRootRef={menuRootRef}
        items={[{ disabled: true, icon: <Trash2 size={18} />, label: "削除する", tone: "danger" }]}
        onOpenChange={onMenuOpenChange}
      />
    </div>
  );
}

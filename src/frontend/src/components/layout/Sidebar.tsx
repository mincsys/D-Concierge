import { History, PanelLeft, Plus, Search, Settings } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { AccountUser } from "@/features/account/model/types";
import { ChatHistoryList } from "@/features/chat/components/ChatHistoryList";
import type { ChatHistoryItem } from "@/features/chat/model/types";
import { cn } from "@/lib/utils";

const brandLogoUrl = new URL("../../assets/d-concierge-logo.png", import.meta.url).href;

export function Sidebar({
  activeChatId,
  collapsed,
  currentUser,
  histories,
  onStartNewChat,
  onOpenAnswer,
  onOpenAccountSettings,
  onRequestDeleteHistoryChat,
  onToggleCollapsed,
}: {
  activeChatId?: string;
  collapsed: boolean;
  currentUser: AccountUser;
  histories: ChatHistoryItem[];
  onStartNewChat: () => void;
  onOpenAnswer: (chatId: string) => void;
  onOpenAccountSettings?: () => void;
  onRequestDeleteHistoryChat?: (chatId: string) => void;
  onToggleCollapsed: () => void;
}) {
  const userInitial = currentUser.userId.charAt(0).toUpperCase();

  if (collapsed) {
    return (
      <aside
        className="sticky top-0 flex h-screen min-h-0 flex-col overflow-hidden border-r border-[var(--dc-border)] bg-linear-to-b from-[var(--dc-sidebar-from)] via-[var(--dc-sidebar-via)] to-[var(--dc-sidebar-to)]"
        aria-label="折りたたみサイドバー"
      >
        <Button
          className="mx-auto mt-[35px] grid size-[34px] place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] hover:bg-transparent hover:text-[var(--dc-muted)]"
          type="button"
          variant="ghost"
          aria-label="サイドバーを展開"
          onClick={onToggleCollapsed}
        >
          <PanelLeft size={28} />
        </Button>

        <Button
          className="mx-auto mt-[35px] grid size-[38px] place-items-center rounded-lg p-0"
          type="button"
          aria-label="新しいチャット"
          onClick={onStartNewChat}
        >
          <Plus size={24} />
        </Button>

        <Button
          className="mx-auto mt-[19px] grid size-[42px] place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] hover:bg-transparent hover:text-[var(--dc-muted)]"
          type="button"
          variant="ghost"
          aria-label="チャットを検索"
        >
          <Search size={26} />
        </Button>

        <Button
          className="mx-auto mt-[21px] grid size-[42px] place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] hover:bg-transparent hover:text-[var(--dc-muted)]"
          type="button"
          variant="ghost"
          aria-label="最近のチャット"
        >
          <History size={27} />
        </Button>

        <Button
          className="mx-auto mt-auto mb-5 grid size-[42px] place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] hover:bg-transparent hover:text-[var(--dc-muted)]"
          type="button"
          variant="ghost"
          aria-label="設定"
          onClick={onOpenAccountSettings}
        >
          <Avatar className="size-[34px] bg-[var(--dc-primary)] text-white">
            <AvatarFallback className="bg-[var(--dc-primary)] text-[14px] font-[760] text-white">
              {userInitial}
            </AvatarFallback>
          </Avatar>
        </Button>
      </aside>
    );
  }

  return (
    <aside className="sticky top-0 flex h-screen min-h-0 flex-col overflow-hidden border-r border-[var(--dc-border)] bg-linear-to-b from-[var(--dc-sidebar-from)] via-[var(--dc-sidebar-via)] to-[var(--dc-sidebar-to)] pt-7">
      <div className="mx-4 mb-6 flex h-12 items-center gap-[13px]">
        <div
          className="grid size-10 shrink-0 place-items-center overflow-hidden"
          aria-hidden="true"
        >
          <img className="h-9 w-auto object-contain" src={brandLogoUrl} alt="" />
        </div>
        <div className="translate-y-[-2px] whitespace-nowrap text-[26px] leading-none font-extrabold tracking-normal text-[var(--dc-primary-strong)]">
          D-Concierge
        </div>
        <Button
          className="ml-auto grid size-[34px] place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] hover:bg-transparent hover:text-[var(--dc-muted)]"
          type="button"
          variant="ghost"
          aria-label="サイドバー切替"
          onClick={onToggleCollapsed}
        >
          <PanelLeft size={28} />
        </Button>
      </div>

      <Button
        className="mx-4 h-[45px] w-auto gap-[11px] rounded-lg text-base font-bold"
        type="button"
        onClick={onStartNewChat}
      >
        <span className="text-[28px] leading-none font-[360]">+</span>
        新しいチャット
      </Button>

      <label className="mx-4 mt-[17px] grid h-[42px] grid-cols-[auto_1fr_auto] items-center gap-3 rounded-[10px] border border-[var(--dc-border)] bg-white px-[10px] pl-3.5 text-[var(--dc-muted)]">
        <Search size={20} />
        <Input
          className="h-auto border-0 bg-transparent p-0 text-[15px] text-[var(--dc-text)] shadow-none placeholder:text-[var(--dc-muted)] focus-visible:ring-0"
          aria-label="チャットを検索"
          placeholder="チャットを検索"
        />
        <kbd className="min-w-8 rounded-[7px] border border-[var(--dc-border)] bg-[var(--dc-primary-softer)] px-[5px] py-[3px] text-center text-xs text-[var(--dc-muted)]">
          ⌘K
        </kbd>
      </label>

      <div
        className={cn(
          "mx-4 mt-[29px] mb-3 flex h-6 items-center gap-2 text-[15px] font-bold text-[var(--dc-muted-strong)]",
          "[&_svg]:text-[var(--dc-muted)]",
        )}
      >
        <History size={20} />
        最近のチャット
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <ChatHistoryList
          activeChatId={activeChatId}
          histories={histories}
          onOpenAnswer={onOpenAnswer}
          onRequestDelete={onRequestDeleteHistoryChat}
        />
      </ScrollArea>

      <button
        className="mt-auto grid min-h-[82px] grid-cols-[38px_1fr_34px] items-center gap-3 border-t border-[var(--dc-border-soft)] bg-[var(--dc-sidebar-to)] px-4 py-3.5 text-left text-base font-[750] hover:bg-[var(--dc-primary-softer)]"
        type="button"
        aria-label="設定"
        onClick={onOpenAccountSettings}
      >
        <Avatar className="size-[38px] bg-[var(--dc-primary)] text-white">
          <AvatarFallback className="bg-[var(--dc-primary)] font-[760] text-white">
            {userInitial}
          </AvatarFallback>
        </Avatar>
        <span className="min-w-0 truncate">{currentUser.userName}</span>
        <span className="grid size-[34px] place-items-center rounded-lg text-[var(--dc-muted-strong)]">
          <Settings size={21} />
        </span>
      </button>
      <Separator className="sr-only" />
    </aside>
  );
}

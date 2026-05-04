import { Search, Settings, Split } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { ChatHistoryList } from "@/features/chat/components/ChatHistoryList";
import type { ChatHistoryItem } from "@/features/chat/model/types";

export function Sidebar({
  histories,
  onOpenAnswer,
}: {
  histories: ChatHistoryItem[];
  onOpenAnswer: () => void;
}) {
  return (
    <aside className="sticky top-0 flex h-screen min-h-0 flex-col overflow-hidden border-r border-[#dbe3f0] bg-linear-to-b from-[#fbfdff] via-[#f7fbff] to-[#f4f8fc] px-4 pt-7">
      <div className="mx-[3px] mb-6 flex h-12 items-center gap-[13px]">
        <div className="brand-mark" aria-hidden="true">
          <span />
        </div>
        <div className="whitespace-nowrap text-[26px] font-[780] tracking-normal">D-Concierge</div>
        <Button
          className="ml-auto grid size-[34px] place-items-center rounded-lg bg-transparent p-0 text-[#667694] hover:bg-transparent hover:text-[#667694]"
          type="button"
          variant="ghost"
          aria-label="サイドバー切替"
        >
          <Split size={21} />
        </Button>
      </div>

      <Button
        className="h-[45px] w-full gap-[11px] rounded-lg bg-linear-to-b from-[#0a64ff] to-[#0046ed] text-base font-bold text-white shadow-[0_10px_18px_rgba(20,90,240,0.22)] hover:from-[#0a64ff] hover:to-[#0046ed]"
        type="button"
      >
        <span className="text-[28px] leading-none font-[360]">+</span>
        新しいチャット
      </Button>

      <label className="mt-[17px] grid h-[42px] grid-cols-[auto_1fr_auto] items-center gap-3 rounded-[10px] border border-[#dfe6f0] bg-white px-[10px] pl-3.5 text-[#73819a]">
        <Search size={20} />
        <Input
          className="h-auto border-0 bg-transparent p-0 text-[15px] text-[#25304a] shadow-none placeholder:text-[#91a0b8] focus-visible:ring-0"
          aria-label="チャットを検索"
          placeholder="チャットを検索"
        />
        <kbd className="min-w-8 rounded-[7px] border border-[#dbe4f3] bg-[#f8fbff] px-[5px] py-[3px] text-center text-xs text-[#74829a]">
          ⌘K
        </kbd>
      </label>

      <div className="mx-1 mt-[29px] mb-3 text-[15px] font-bold text-[#65718a]">最近のチャット</div>
      <ScrollArea className="min-h-0 flex-1">
        <ChatHistoryList histories={histories} onOpenAnswer={onOpenAnswer} />
      </ScrollArea>

      <div className="mt-auto -mx-4 grid min-h-[82px] grid-cols-[38px_1fr_34px] items-center gap-3 border-t border-[#e0e7f1] bg-[#f4f8fc] px-4 py-3.5 text-base font-[750]">
        <Avatar className="size-[38px] bg-[#cfe9ff] text-[#0f3b90]">
          <AvatarFallback className="bg-[#cfe9ff] font-[760]">A</AvatarFallback>
        </Avatar>
        <span>山田 太郎</span>
        <Button
          className="grid size-[34px] place-items-center rounded-lg bg-transparent p-0 text-[#51617c] hover:bg-transparent hover:text-[#51617c]"
          type="button"
          variant="ghost"
          aria-label="設定"
        >
          <Settings size={21} />
        </Button>
      </div>
      <Separator className="sr-only" />
    </aside>
  );
}

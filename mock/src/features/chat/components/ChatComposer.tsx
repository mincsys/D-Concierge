import { Paperclip, Send, SlidersHorizontal } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type ChatComposerProps = {
  placeholder: string;
  autoFocus?: boolean;
  className?: string;
  focusSignal?: number;
  onSubmit: (message: string) => void;
  onValueChange?: (message: string) => void;
  onFocus?: () => void;
  value?: string;
};

export function ChatComposer({
  placeholder,
  autoFocus = false,
  className,
  focusSignal,
  onSubmit,
  onValueChange,
  onFocus,
  value,
}: ChatComposerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [internalMessage, setInternalMessage] = useState("");
  const message = value ?? internalMessage;
  const canSubmit = message.trim().length > 0;

  useEffect(() => {
    if (focusSignal === undefined) {
      return;
    }
    inputRef.current?.focus();
  }, [focusSignal]);

  function updateMessage(nextMessage: string) {
    if (onValueChange) {
      onValueChange(nextMessage);
      return;
    }
    setInternalMessage(nextMessage);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    onSubmit(trimmed);
    updateMessage("");
  }

  return (
    <form
      className={cn(
        "grid h-[66px] grid-cols-[auto_1fr_auto_auto] items-center gap-[17px] rounded-[11px] border border-[#dce4f0] bg-white/95 pr-[15px] pl-[17px] text-[#60708d] shadow-[0_10px_30px_rgba(23,36,61,0.05)] backdrop-blur-[10px]",
        className,
      )}
      onSubmit={handleSubmit}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            className="grid size-[30px] place-items-center rounded-full bg-transparent p-0 text-[#60708d] shadow-none hover:bg-[#eef4ff] hover:text-[#31517f]"
            type="button"
            variant="ghost"
            aria-label="ファイルを添付"
          >
            <Paperclip size={23} />
          </Button>
        </TooltipTrigger>
        <TooltipContent>ファイルを添付</TooltipContent>
      </Tooltip>
      <Input
        ref={inputRef}
        autoFocus={autoFocus}
        className="h-auto border-0 bg-transparent p-0 text-base font-[560] text-[#1f2a44] shadow-none placeholder:text-[#9aa6ba] focus-visible:ring-0"
        placeholder={placeholder}
        value={message}
        onChange={(event) => updateMessage(event.target.value)}
        onFocus={onFocus}
      />
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            className={cn(
              "grid size-[42px] rounded-full bg-transparent p-0 text-[#52627f] shadow-none hover:bg-transparent hover:text-[#52627f]",
            )}
            type="button"
            variant="ghost"
            aria-label="表示設定"
          >
            <SlidersHorizontal size={24} />
          </Button>
        </TooltipTrigger>
        <TooltipContent>表示設定</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            className={cn(
              "grid size-11 rounded-xl bg-[#075bff] p-0 text-white shadow-[0_10px_20px_rgba(7,91,255,0.22)] hover:bg-[#075bff] disabled:bg-[#bfc8d8] disabled:text-white disabled:opacity-100 disabled:shadow-none disabled:hover:bg-[#bfc8d8]",
            )}
            type="submit"
            aria-label="送信"
            disabled={!canSubmit}
          >
            <Send size={22} fill="currentColor" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>送信</TooltipContent>
      </Tooltip>
    </form>
  );
}

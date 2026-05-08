import { LoaderCircle, Paperclip, Send, SlidersHorizontal, Square } from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const MIN_TEXTAREA_HEIGHT = 42;
const MAX_TEXTAREA_HEIGHT = 480;
const COMPOSER_PLACEHOLDER = "指示を入力してください";

type ChatComposerProps = {
  actionMode?: "send" | "cancel" | "canceling";
  autoFocus?: boolean;
  className?: string;
  focusSignal?: number;
  onCancel?: () => void;
  onSubmit: (message: string) => void;
  onValueChange?: (message: string) => void;
  onFocus?: () => void;
  value?: string;
};

export function ChatComposer({
  actionMode = "send",
  autoFocus = false,
  className,
  focusSignal,
  onCancel,
  onSubmit,
  onValueChange,
  onFocus,
  value,
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [internalMessage, setInternalMessage] = useState("");
  const message = value ?? internalMessage;
  const canSubmit = message.trim().length > 0;
  const actionLabel =
    actionMode === "canceling" ? "キャンセル処理中" : actionMode === "cancel" ? "キャンセル" : "送信";
  const actionTooltip =
    actionMode === "canceling" ? "キャンセル処理中" : actionMode === "cancel" ? "キャンセル" : "送信（Ctrl+Enter）";
  const actionDisabled = actionMode === "send" ? !canSubmit : actionMode === "canceling";

  useLayoutEffect(() => {
    resizeTextarea();
  }, [message]);

  useEffect(() => {
    if (focusSignal === undefined) {
      return;
    }
    textareaRef.current?.focus();
  }, [focusSignal]);

  function resizeTextarea() {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    textarea.style.height = `${MIN_TEXTAREA_HEIGHT}px`;
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, MIN_TEXTAREA_HEIGHT), MAX_TEXTAREA_HEIGHT);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > MAX_TEXTAREA_HEIGHT ? "auto" : "hidden";
  }

  function updateMessage(nextMessage: string) {
    if (onValueChange) {
      onValueChange(nextMessage);
      return;
    }
    setInternalMessage(nextMessage);
  }

  function submitMessage() {
    if (actionMode !== "send") {
      return;
    }
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    onSubmit(trimmed);
    updateMessage("");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (actionMode === "cancel") {
      onCancel?.();
      return;
    }
    submitMessage();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || (!event.ctrlKey && !event.metaKey)) {
      return;
    }

    event.preventDefault();
    submitMessage();
  }

  return (
    <form
      className={cn(
        "grid min-h-[66px] grid-cols-[auto_minmax(0,1fr)_auto_auto] items-end gap-[17px] rounded-[11px] border border-[var(--dc-border)] bg-white/95 py-[10px] pr-[15px] pl-[17px] text-[var(--dc-muted)] shadow-[0_10px_30px_var(--dc-shadow-soft)] backdrop-blur-[10px]",
        className,
      )}
      onSubmit={handleSubmit}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            className="mb-[6px] grid size-[30px] place-items-center rounded-full bg-transparent p-0 text-[var(--dc-primary)] shadow-none hover:bg-[var(--dc-primary-hover)] hover:text-[var(--dc-primary-strong)]"
            type="button"
            variant="ghost"
            aria-label="ファイルを添付"
          >
            <Paperclip size={23} />
          </Button>
        </TooltipTrigger>
        <TooltipContent>ファイルを添付</TooltipContent>
      </Tooltip>
      <textarea
        ref={textareaRef}
        autoFocus={autoFocus}
        className="min-h-[42px] w-full resize-none overflow-hidden border-0 bg-transparent px-0 py-[9px] text-base leading-6 font-[560] whitespace-pre-wrap text-[var(--dc-text)] shadow-none break-words placeholder:text-[var(--dc-muted)] focus-visible:ring-0 focus-visible:outline-none"
        placeholder={COMPOSER_PLACEHOLDER}
        rows={1}
        value={message}
        onChange={(event) => updateMessage(event.target.value)}
        onFocus={onFocus}
        onKeyDown={handleKeyDown}
      />
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            className={cn(
              "grid size-[42px] rounded-full bg-transparent p-0 text-[var(--dc-primary)] shadow-none hover:bg-transparent hover:text-[var(--dc-primary-strong)]",
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
              "grid size-11 rounded-xl bg-[var(--dc-primary)] p-0 text-white shadow-[0_10px_20px_var(--dc-shadow-primary)] hover:bg-[var(--dc-primary)] disabled:bg-[var(--dc-muted)] disabled:text-white disabled:opacity-100 disabled:shadow-none disabled:hover:bg-[var(--dc-muted)]",
            )}
            type={actionMode === "send" ? "submit" : "button"}
            aria-label={actionLabel}
            disabled={actionDisabled}
            onClick={actionMode === "cancel" ? onCancel : undefined}
          >
            {actionMode === "canceling" ? (
              <LoaderCircle className="animate-spin" size={22} />
            ) : actionMode === "cancel" ? (
              <Square size={18} fill="currentColor" />
            ) : (
              <Send size={22} fill="currentColor" />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>{actionTooltip}</TooltipContent>
      </Tooltip>
    </form>
  );
}

import { type ReactNode, type RefObject, useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

export type ActionMenuItem = {
  disabled?: boolean;
  icon: ReactNode;
  label: string;
  tone?: "default" | "danger";
};

export function ActionMenuPopover({
  ariaLabel,
  className,
  dismissRootRef,
  items,
  open,
  onOpenChange,
}: {
  ariaLabel: string;
  className?: string;
  dismissRootRef?: RefObject<HTMLElement | null>;
  items: ActionMenuItem[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      const root = dismissRootRef?.current ?? menuRef.current;
      if (root?.contains(event.target as Node)) {
        return;
      }
      onOpenChange(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onOpenChange(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [dismissRootRef, onOpenChange, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className={cn(
        "absolute top-[42px] right-0 w-[188px] rounded-[14px] border border-[var(--dc-border)] bg-[rgba(255,255,255,0.98)] p-2.5 text-[var(--dc-text)] shadow-[0_18px_44px_rgba(25,42,70,0.18)] backdrop-blur-[10px]",
        className,
      )}
      ref={menuRef}
      role="menu"
      aria-label={ariaLabel}
    >
      {items.map((item) => (
        <div
          className={cn(
            "flex min-h-10 items-center gap-3 rounded-[10px] px-3 text-[14px] leading-5 font-[700]",
            item.tone === "danger" ? "text-[var(--dc-danger)]" : "text-[var(--dc-text)]",
          )}
          key={item.label}
          role="menuitem"
          aria-disabled={item.disabled ? "true" : undefined}
        >
          {item.icon}
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

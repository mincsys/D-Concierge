import { MoreHorizontal, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

export function TopMenu() {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (menuRef.current?.contains(event.target as Node)) {
        return;
      }
      setOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className="absolute top-[27px] right-[25px] z-3" ref={menuRef}>
      <Button
        className="grid h-8 w-[38px] place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] hover:bg-[var(--dc-primary-softer)] hover:text-[var(--dc-primary-strong)]"
        type="button"
        variant="ghost"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="その他"
        onClick={() => setOpen((current) => !current)}
      >
        <MoreHorizontal size={24} />
      </Button>
      {open ? (
        <div
          className="absolute top-[42px] right-0 w-[188px] rounded-[14px] border border-[var(--dc-border)] bg-[rgba(255,255,255,0.98)] p-2.5 text-[var(--dc-text)] shadow-[0_18px_44px_rgba(25,42,70,0.18)] backdrop-blur-[10px]"
          role="menu"
          aria-label="その他メニュー"
        >
          <div
            className="flex min-h-10 items-center gap-3 rounded-[10px] px-3 text-[14px] leading-5 font-[700] text-[var(--dc-danger)]"
            role="menuitem"
            aria-disabled="true"
          >
            <Trash2 size={18} />
            <span>削除する</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

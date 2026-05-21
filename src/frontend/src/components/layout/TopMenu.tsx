import { MoreHorizontal, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { ActionMenuPopover } from "@/components/action-menu/ActionMenuPopover";
import { Button } from "@/components/ui/button";

export function TopMenu({
  deleteDisabled = false,
  onRequestDelete,
}: {
  deleteDisabled?: boolean;
  onRequestDelete?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

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
      <ActionMenuPopover
        open={open}
        ariaLabel="その他メニュー"
        dismissRootRef={menuRef}
        items={[
          {
            disabled: deleteDisabled || !onRequestDelete,
            icon: <Trash2 size={18} />,
            label: "削除する",
            onSelect: onRequestDelete,
            tone: "danger",
          },
        ]}
        onOpenChange={setOpen}
      />
    </div>
  );
}

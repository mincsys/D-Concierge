import { MoreHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";

export function TopMenu() {
  return (
    <Button
      className="absolute top-[27px] right-[25px] z-3 grid h-8 w-[38px] place-items-center rounded-lg bg-transparent p-0 text-[var(--dc-muted)] hover:bg-transparent hover:text-[var(--dc-muted)]"
      type="button"
      variant="ghost"
      aria-label="その他"
    >
      <MoreHorizontal size={24} />
    </Button>
  );
}

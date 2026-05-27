import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

export function SettingsShell({
  children,
  onBack,
  onOpenChange,
  open,
  title,
}: {
  children: ReactNode;
  onBack?: () => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  title: string;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid w-[min(680px,calc(100%-32px))] grid-cols-[190px_minmax(0,1fr)] gap-0 overflow-hidden bg-[var(--dc-app-bg)] p-0">
        <aside className="border-r border-[var(--dc-border-soft)] bg-linear-to-b from-[var(--dc-sidebar-from)] via-[var(--dc-sidebar-via)] to-[var(--dc-sidebar-to)]">
          <div
            className="flex min-h-[68px] items-center border-b border-[var(--dc-border-soft)] px-5 text-lg font-[780] text-[var(--dc-text-strong)]"
            data-testid="settings-sidebar-header"
          >
            <DialogTitle className="text-lg leading-none font-[780]">設定</DialogTitle>
          </div>
          <SettingsMenu />
        </aside>
        <section className="min-h-[430px] bg-[var(--dc-app-bg)]">
          <SettingsHeader title={title} onBack={onBack} />
          <div className="px-5 pt-0 pb-5" data-testid="settings-main-content">
            {children}
          </div>
        </section>
      </DialogContent>
    </Dialog>
  );
}

function SettingsHeader({ onBack, title }: { onBack?: () => void; title: string }) {
  return (
    <div
      className="relative flex min-h-[68px] items-center gap-3 px-5 text-lg font-[780] text-[var(--dc-text-strong)] after:absolute after:right-5 after:bottom-0 after:left-5 after:border-b after:border-[var(--dc-border-soft)]"
      data-testid="settings-main-header"
    >
      {onBack ? (
        <Button
          className="grid size-9 place-items-center rounded-lg bg-transparent p-0"
          type="button"
          variant="ghost"
          aria-label="戻る"
          onClick={onBack}
        >
          <ArrowLeft size={22} />
        </Button>
      ) : null}
      <h2 className="text-lg leading-none font-[780]">{title}</h2>
    </div>
  );
}

function SettingsMenu() {
  return (
    <div className="min-h-[46px] border-b border-l-[5px] border-b-[var(--dc-border-soft)] border-l-[var(--dc-primary)] bg-transparent px-5 py-3 pl-[22px] text-[15.5px] font-[620] text-[var(--dc-primary)]">
      アカウント
    </div>
  );
}

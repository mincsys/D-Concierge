import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const rowClassName =
  "grid min-h-[60px] items-center gap-3 border-b border-[var(--dc-border-soft)] last:border-b-0";

export function DisplaySettingsRow({ label, value }: { label: string; value: string }) {
  return (
    <div className={cn(rowClassName, "grid-cols-[minmax(0,1fr)_auto_auto]")}>
      <span className="min-w-0 truncate text-[15px] text-[var(--dc-text-strong)]">{label}</span>
      <span className="min-w-0 truncate">{value}</span>
      <span className="ml-5 w-6" aria-hidden="true" />
    </div>
  );
}

export function NavigationSettingsRow({
  label,
  value,
  onClick,
}: {
  label: string;
  value?: string;
  onClick: () => void;
}) {
  return (
    <Button
      className={cn(
        rowClassName,
        "w-full grid-cols-[minmax(0,1fr)_auto_auto] rounded-none bg-transparent px-0 text-left text-[15px] font-[760] text-[var(--dc-text-strong)] shadow-none hover:bg-[var(--dc-primary-hover)]",
      )}
      type="button"
      variant="ghost"
      onClick={onClick}
    >
      <span className="min-w-0 truncate">{label}</span>
      {value ? <span className="min-w-0 truncate">{value}</span> : <span />}
      <ChevronRight className="ml-5 text-[var(--dc-muted-strong)]" size={24} />
    </Button>
  );
}

export function ActionSettingsRow({
  actionLabel,
  buttonLabel,
  danger = false,
  icon,
  label,
  onClick,
}: {
  actionLabel?: string;
  buttonLabel: string;
  danger?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <div className={cn(rowClassName, "grid-cols-[minmax(0,1fr)_auto] gap-4")}>
      <span className="min-w-0 truncate text-[15px] text-[var(--dc-text-strong)]">{label}</span>
      <Button
        className={cn("gap-2", danger ? "px-4" : undefined)}
        type="button"
        variant={danger ? "destructive" : undefined}
        aria-label={actionLabel ?? buttonLabel}
        onClick={onClick}
      >
        {icon}
        {buttonLabel}
      </Button>
    </div>
  );
}

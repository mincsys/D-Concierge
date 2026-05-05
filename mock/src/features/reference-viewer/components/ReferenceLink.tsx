import { Button } from "@/components/ui/button";

export function ReferenceLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button
      className="mt-px block h-auto w-fit bg-transparent p-0 text-left text-sm font-bold text-[var(--dc-primary)] shadow-none hover:bg-transparent hover:text-[var(--dc-primary-strong)] hover:underline"
      type="button"
      variant="ghost"
      onClick={onClick}
    >
      {label}
    </Button>
  );
}

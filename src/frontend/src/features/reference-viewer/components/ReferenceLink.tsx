import { Button } from "@/components/ui/button";

export function ReferenceLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button
      className="mt-px block h-auto w-full max-w-full min-w-0 break-words whitespace-normal bg-transparent p-0 text-left text-sm font-bold text-[var(--dc-primary)] shadow-none [overflow-wrap:anywhere] hover:bg-transparent hover:text-[var(--dc-primary-strong)] hover:underline"
      type="button"
      variant="ghost"
      onClick={onClick}
    >
      {label}
    </Button>
  );
}

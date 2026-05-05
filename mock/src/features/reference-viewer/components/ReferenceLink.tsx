import { Button } from "@/components/ui/button";

export function ReferenceLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button
      className="mt-px block h-auto w-fit bg-transparent p-0 text-left text-sm font-bold text-[#0a64ff] shadow-none hover:bg-transparent hover:text-[#0046ed] hover:underline"
      type="button"
      variant="ghost"
      onClick={onClick}
    >
      {label}
    </Button>
  );
}

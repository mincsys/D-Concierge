import { Dialog, DialogClose, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatPdfPageRange } from "@/features/reference-viewer/lib/pageRange";
import type { PdfReference } from "@/features/reference-viewer/model/types";
import { PdfPageViewer } from "@/features/reference-viewer/viewers/PdfPageViewer";

export function ReferenceViewerDialog({
  open,
  reference,
  onOpenChange,
}: {
  open: boolean;
  reference: PdfReference | null;
  onOpenChange: (open: boolean) => void;
}) {
  if (!reference) {
    return null;
  }

  const pageRangeLabel = formatPdfPageRange(reference);
  const dialogDescription = `${reference.label} PDF ${pageRangeLabel}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[98vh] w-[min(980px,98vw)] max-w-none flex-col gap-0 overflow-hidden rounded-[14px] bg-white p-0 shadow-[0_26px_80px_rgba(0,0,0,0.26)]"
        aria-label="参照元PDF"
      >
        <header className="grid grid-cols-[1fr_auto] items-center gap-[18px] border-b border-[var(--dc-border-soft)] px-5 pt-4 pb-3">
          <DialogHeader>
            <span className="text-xs font-[820] text-[var(--dc-primary)]">参照元PDF</span>
            <DialogTitle className="mt-[3px] text-xl leading-[1.3] font-bold">
              {reference.label}
            </DialogTitle>
            <DialogDescription className="sr-only">{dialogDescription}</DialogDescription>
          </DialogHeader>
          <DialogClose />
        </header>
        <PdfPageViewer reference={reference} />
      </DialogContent>
    </Dialog>
  );
}

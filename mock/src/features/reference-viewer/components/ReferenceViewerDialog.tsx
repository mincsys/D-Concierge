import { useCallback, useState } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { pdfReference } from "@/features/reference-viewer/model/types";
import { PdfPageViewer } from "@/features/reference-viewer/viewers/PdfPageViewer";

export function ReferenceViewerDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [status, setStatus] = useState(`${pdfReference.description}を読み込んでいます。`);
  const handleStatusChange = useCallback((nextStatus: string) => {
    setStatus(nextStatus);
  }, []);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[92vh] w-[min(980px,92vw)] max-w-none flex-col gap-0 overflow-hidden rounded-[14px] bg-white p-0 shadow-[0_26px_80px_rgba(0,0,0,0.26)]"
        aria-label="参照元PDF"
      >
        <header className="grid grid-cols-[1fr_auto] items-start gap-[18px] border-b border-[#e2e8f2] px-5 pt-[18px] pb-[15px]">
          <DialogHeader>
            <span className="text-xs font-[820] text-[#0a64ff]">参照元PDF</span>
            <DialogTitle className="mt-[3px] mb-[5px] text-xl leading-[1.3] font-bold">
              {pdfReference.title}
            </DialogTitle>
            <DialogDescription className="sr-only">{pdfReference.description}</DialogDescription>
            <p id="pdf-viewer-status" className="m-0 text-sm font-[650] text-[#5c6b86]">
              {status}
            </p>
          </DialogHeader>
        </header>
        <PdfPageViewer reference={pdfReference} onStatusChange={handleStatusChange} />
      </DialogContent>
    </Dialog>
  );
}

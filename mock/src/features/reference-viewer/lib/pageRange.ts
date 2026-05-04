import type { PdfReference } from "@/features/reference-viewer/model/types";

export function formatPdfPageRange(reference: Pick<PdfReference, "startPage" | "endPage">) {
  if (reference.startPage === reference.endPage) {
    return `p.${reference.startPage}`;
  }

  return `p.${reference.startPage}-${reference.endPage}`;
}

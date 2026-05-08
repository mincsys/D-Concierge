import type { PdfReference } from "@/features/reference-viewer/model/types";

export function formatPdfPageRange(reference: Pick<PdfReference, "locator">) {
  if (reference.locator.page_start === reference.locator.page_end) {
    return `p.${reference.locator.page_start}`;
  }

  return `p.${reference.locator.page_start}-${reference.locator.page_end}`;
}

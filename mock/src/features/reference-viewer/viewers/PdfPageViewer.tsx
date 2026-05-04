import { useEffect, useRef } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";

import type { PdfReference } from "@/features/reference-viewer/model/types";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfPageViewer({
  reference,
  onStatusChange,
}: {
  reference: PdfReference;
  onStatusChange: (status: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);

  useEffect(() => {
    let destroyed = false;
    let pdfDoc: PDFDocumentProxy | null = null;
    onStatusChange(`${reference.description}を読み込んでいます。`);

    async function renderPdf() {
      try {
        const loadingTask = pdfjsLib.getDocument(reference.url);
        pdfDoc = await loadingTask.promise;
        const page = await pdfDoc.getPage(reference.pageNumber);
        const canvas = canvasRef.current;
        if (!canvas || destroyed) {
          return;
        }

        const containerWidth = Math.min(850, Math.max(620, canvas.parentElement?.clientWidth ?? 760));
        const viewport = page.getViewport({ scale: 1 });
        const scale = containerWidth / viewport.width;
        const scaledViewport = page.getViewport({ scale });
        const pixelRatio = window.devicePixelRatio || 1;
        const context = canvas.getContext("2d");
        if (!context) {
          throw new Error("Canvas contextを取得できません。");
        }

        canvas.width = Math.floor(scaledViewport.width * pixelRatio);
        canvas.height = Math.floor(scaledViewport.height * pixelRatio);
        canvas.style.width = `${Math.floor(scaledViewport.width)}px`;
        canvas.style.height = `${Math.floor(scaledViewport.height)}px`;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

        renderTaskRef.current = page.render({ canvas, canvasContext: context, viewport: scaledViewport });
        await renderTaskRef.current.promise;
        if (!destroyed) {
          onStatusChange(reference.description);
        }
      } catch (error) {
        if (!destroyed) {
          onStatusChange(error instanceof Error ? error.message : "PDFを表示できませんでした。");
        }
      }
    }

    void renderPdf();

    return () => {
      destroyed = true;
      renderTaskRef.current?.cancel();
      pdfDoc?.destroy();
    };
  }, [onStatusChange, reference]);

  return (
    <div className="pdf-canvas-wrap">
      <canvas ref={canvasRef} data-testid="pdf-canvas" />
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { RefObject } from "react";
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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const targetPageRef = useRef<HTMLDivElement | null>(null);
  const didScrollToTargetRef = useRef(false);
  const didRenderTargetRef = useRef(false);
  const renderedPagesRef = useRef<Set<number>>(new Set());
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [containerWidth, setContainerWidth] = useState(760);
  const [pagesToRender, setPagesToRender] = useState<Set<number>>(() => new Set());
  const targetPageNumber = useMemo(() => {
    if (!pdfDoc) {
      return reference.pageNumber;
    }
    return Math.min(Math.max(1, reference.pageNumber), pdfDoc.numPages);
  }, [pdfDoc, reference.pageNumber]);

  useEffect(() => {
    let destroyed = false;
    let loadedPdfDoc: PDFDocumentProxy | null = null;
    didScrollToTargetRef.current = false;
    didRenderTargetRef.current = false;
    renderedPagesRef.current = new Set();
    setPdfDoc(null);
    setPagesToRender(new Set());
    onStatusChange("PDFを読み込んでいます。");

    async function loadPdf() {
      try {
        const loadingTask = pdfjsLib.getDocument(reference.url);
        loadedPdfDoc = await loadingTask.promise;
        if (destroyed) {
          return;
        }
        setPdfDoc(loadedPdfDoc);
        const normalizedTargetPage = Math.min(Math.max(1, reference.pageNumber), loadedPdfDoc.numPages);
        setPagesToRender(createInitialPagesToRender(normalizedTargetPage, loadedPdfDoc.numPages));
        const nextContainerWidth = Math.min(
          850,
          Math.max(620, (containerRef.current?.clientWidth ?? 804) - 44),
        );
        setContainerWidth(nextContainerWidth);
        onStatusChange("PDFを表示しています。");
      } catch (error) {
        if (!destroyed) {
          onStatusChange(error instanceof Error ? error.message : "PDFを表示できませんでした。");
        }
      }
    }

    void loadPdf();

    return () => {
      destroyed = true;
      loadedPdfDoc?.destroy();
    };
  }, [onStatusChange, reference]);

  const handlePageRendered = useCallback((pageNumber: number) => {
    if (renderedPagesRef.current.has(pageNumber)) {
      return;
    }

    renderedPagesRef.current = new Set(renderedPagesRef.current).add(pageNumber);
    if (pageNumber === targetPageNumber) {
      didRenderTargetRef.current = true;
      onStatusChange("参照元ページを表示しました。");
    } else if (!didRenderTargetRef.current) {
      onStatusChange("PDFを表示しています。");
    }

    if (pageNumber === targetPageNumber && !didScrollToTargetRef.current) {
      didScrollToTargetRef.current = true;
      requestAnimationFrame(() => {
        const container = containerRef.current;
        const target = targetPageRef.current;
        if (!container || !target) {
          return;
        }
        container.scrollTo({
          top: Math.max(0, target.offsetTop - container.offsetTop - 8),
          behavior: "auto",
        });
      });
    }
  }, [onStatusChange, targetPageNumber]);

  const handlePageVisible = useCallback((pageNumber: number) => {
    setPagesToRender((current) => {
      if (current.has(pageNumber)) {
        return current;
      }
      const next = new Set(current);
      next.add(pageNumber);
      return next;
    });
  }, []);

  return (
    <div className="pdf-canvas-wrap" ref={containerRef}>
      {pdfDoc
        ? Array.from({ length: pdfDoc.numPages }, (_, index) => {
            const pageNumber = index + 1;
            const isTargetPage = pageNumber === targetPageNumber;
            return (
              <div
                className={isTargetPage ? "pdf-page-frame pdf-page-frame-target" : "pdf-page-frame"}
                data-page-number={pageNumber}
                key={pageNumber}
                ref={isTargetPage ? targetPageRef : undefined}
              >
                <PdfPageFrame
                  containerWidth={containerWidth}
                  isTargetPage={isTargetPage}
                  shouldRender={pagesToRender.has(pageNumber)}
                  pageNumber={pageNumber}
                  pdfDoc={pdfDoc}
                  rootRef={containerRef}
                  onRendered={handlePageRendered}
                  onVisible={handlePageVisible}
                />
              </div>
            );
          })
        : null}
    </div>
  );
}

function createInitialPagesToRender(targetPageNumber: number, totalPages: number) {
  const pageNumbers = [
    targetPageNumber,
    targetPageNumber - 1,
    targetPageNumber + 1,
  ].filter((pageNumber) => pageNumber >= 1 && pageNumber <= totalPages);

  return new Set(pageNumbers);
}

function PdfPageFrame({
  containerWidth,
  isTargetPage,
  onRendered,
  onVisible,
  pageNumber,
  pdfDoc,
  rootRef,
  shouldRender,
}: {
  containerWidth: number;
  isTargetPage: boolean;
  onRendered: (pageNumber: number) => void;
  onVisible: (pageNumber: number) => void;
  pageNumber: number;
  pdfDoc: PDFDocumentProxy;
  rootRef: RefObject<HTMLDivElement | null>;
  shouldRender: boolean;
}) {
  const frameContentRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = frameContentRef.current;
    const root = rootRef.current;
    if (!element || !root || shouldRender) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          onVisible(pageNumber);
          observer.disconnect();
        }
      },
      {
        root,
        rootMargin: "900px 0px",
        threshold: 0.01,
      },
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [onVisible, pageNumber, rootRef, shouldRender]);

  return (
    <div ref={frameContentRef}>
      <div className="pdf-page-label">
        {isTargetPage ? `参照元ページ p.${pageNumber}` : `p.${pageNumber}`}
      </div>
      {shouldRender ? (
        <PdfPageCanvas
          containerWidth={containerWidth}
          pageNumber={pageNumber}
          pdfDoc={pdfDoc}
          onRendered={onRendered}
        />
      ) : (
        <div
          className="pdf-page-placeholder"
          style={{
            height: `${Math.round(containerWidth * 1.42)}px`,
            width: `${containerWidth}px`,
          }}
        >
          <span>p.{pageNumber}</span>
        </div>
      )}
    </div>
  );
}

function PdfPageCanvas({
  containerWidth,
  pageNumber,
  pdfDoc,
  onRendered,
}: {
  containerWidth: number;
  pageNumber: number;
  pdfDoc: PDFDocumentProxy;
  onRendered: (pageNumber: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);

  useEffect(() => {
    let destroyed = false;

    async function renderPage() {
      const page = await pdfDoc.getPage(pageNumber);
      const canvas = canvasRef.current;
      if (!canvas || destroyed) {
        return;
      }

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
        onRendered(pageNumber);
      }
    }

    void renderPage();

    return () => {
      destroyed = true;
      renderTaskRef.current?.cancel();
    };
  }, [containerWidth, onRendered, pageNumber, pdfDoc]);

  return <canvas ref={canvasRef} data-testid="pdf-canvas" />;
}

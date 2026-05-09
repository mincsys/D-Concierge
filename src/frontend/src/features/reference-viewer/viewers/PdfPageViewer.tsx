import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { RefObject } from "react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";

import type { PdfReference } from "@/features/reference-viewer/model/types";
import { cn } from "@/lib/utils";

type PageRange = {
  pageStart: number;
  pageEnd: number;
};

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfPageViewer({ reference }: { reference: PdfReference }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const targetPageRef = useRef<HTMLDivElement | null>(null);
  const didScrollToTargetRef = useRef(false);
  const renderedPagesRef = useRef<Set<number>>(new Set());
  const [errorMessage, setErrorMessage] = useState("");
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [containerWidth, setContainerWidth] = useState(760);
  const [pagesToRender, setPagesToRender] = useState<Set<number>>(() => new Set());
  const referencePageRange = useMemo(
    () => (pdfDoc ? getValidPdfPageRange(reference, pdfDoc.numPages) : null),
    [pdfDoc, reference],
  );
  const referencePages = useMemo(() => createPages(referencePageRange), [referencePageRange]);
  const referencePageSet = useMemo(() => new Set(referencePages), [referencePages]);

  useEffect(() => {
    let destroyed = false;
    let loadedPdfDoc: PDFDocumentProxy | null = null;
    didScrollToTargetRef.current = false;
    renderedPagesRef.current = new Set();
    setErrorMessage("");
    setPdfDoc(null);
    setPagesToRender(new Set());

    async function loadPdf() {
      try {
        const loadingTask = pdfjsLib.getDocument(reference.url);
        loadedPdfDoc = await loadingTask.promise;
        if (destroyed) {
          return;
        }
        setPdfDoc(loadedPdfDoc);
        const validPageRange = getValidPdfPageRange(reference, loadedPdfDoc.numPages);
        setPagesToRender(createInitialPagesToRender(validPageRange, loadedPdfDoc.numPages));
        const nextContainerWidth = Math.min(
          850,
          Math.max(620, (containerRef.current?.clientWidth ?? 804) - 44),
        );
        setContainerWidth(nextContainerWidth);
      } catch {
        if (!destroyed) {
          setErrorMessage("参照元を表示できませんでした。");
        }
      }
    }

    void loadPdf();

    return () => {
      destroyed = true;
      loadedPdfDoc?.destroy();
    };
  }, [reference]);

  const handlePageRendered = useCallback(
    (page: number) => {
      if (renderedPagesRef.current.has(page)) {
        return;
      }

      renderedPagesRef.current = new Set(renderedPagesRef.current).add(page);

      if (page === referencePageRange?.pageStart && !didScrollToTargetRef.current) {
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
    },
    [referencePageRange?.pageStart],
  );

  const handlePageVisible = useCallback((page: number) => {
    setPagesToRender((current) => {
      if (current.has(page)) {
        return current;
      }
      const next = new Set(current);
      next.add(page);
      return next;
    });
  }, []);

  return (
    <div
      className="pdf-canvas-wrap relative flex flex-1 flex-col gap-[22px] overflow-auto bg-[var(--dc-panel)] p-[22px] text-center"
      ref={containerRef}
    >
      {errorMessage ? (
        <div className="m-auto w-[min(760px,100%)] rounded-lg border border-[#f2b8b8] bg-[#fff6f6] px-5 py-[18px] text-left text-sm font-[720] text-[#9f1d1d]">
          {errorMessage}
        </div>
      ) : null}
      {pdfDoc && !referencePageRange ? (
        <div className="mx-auto w-[min(760px,100%)] rounded-lg border border-[#f2b8b8] bg-[#fff6f6] px-5 py-[14px] text-left text-sm font-[720] text-[#9f1d1d]">
          参照元の位置情報を表示できませんでした。
        </div>
      ) : null}
      {pdfDoc
        ? Array.from({ length: pdfDoc.numPages }, (_, index) => {
            const page = index + 1;
            const isReferencePage = referencePageSet.has(page);
            return (
              <div
                className={cn(
                  "pdf-page-frame mx-auto w-fit max-w-full scroll-mt-3 rounded-xl border border-transparent p-2.5",
                  isReferencePage &&
                    "pdf-page-frame-target border-[var(--dc-primary)] bg-[rgba(15,85,173,0.1)] shadow-[0_0_0_3px_rgba(15,85,173,0.14)]",
                )}
                data-page-number={page}
                key={page}
                ref={page === referencePageRange?.pageStart ? targetPageRef : undefined}
              >
                <PdfPageFrame
                  containerWidth={containerWidth}
                  isReferencePage={isReferencePage}
                  shouldRender={pagesToRender.has(page)}
                  page={page}
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

function getValidPdfPageRange(reference: PdfReference, totalPages: number): PageRange | null {
  const pageStart = reference.locator.page_start;
  const pageEnd = reference.locator.page_end;
  if (pageStart < 1 || pageEnd < pageStart || pageEnd > totalPages) {
    return null;
  }

  return { pageStart, pageEnd };
}

function createPages(pageRange: PageRange | null) {
  if (!pageRange) {
    return [];
  }

  return Array.from(
    { length: pageRange.pageEnd - pageRange.pageStart + 1 },
    (_, index) => pageRange.pageStart + index,
  );
}

function createInitialPagesToRender(pageRange: PageRange | null, totalPages: number) {
  const pages = pageRange
    ? [pageRange.pageStart - 1, ...createPages(pageRange), pageRange.pageEnd + 1].filter(
        (page) => page >= 1 && page <= totalPages,
      )
    : [1].filter((page) => page <= totalPages);

  return new Set(pages);
}

function PdfPageFrame({
  containerWidth,
  isReferencePage,
  onRendered,
  onVisible,
  page,
  pdfDoc,
  rootRef,
  shouldRender,
}: {
  containerWidth: number;
  isReferencePage: boolean;
  onRendered: (page: number) => void;
  onVisible: (page: number) => void;
  page: number;
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
          onVisible(page);
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
  }, [onVisible, page, rootRef, shouldRender]);

  return (
    <div ref={frameContentRef}>
      <div
        className={cn(
          "mb-2 text-left text-[13px] font-[780] text-[var(--dc-muted-strong)]",
          isReferencePage && "text-[var(--dc-primary)]",
        )}
      >
        {isReferencePage ? `参照元ページ p.${page}` : `p.${page}`}
      </div>
      {shouldRender ? (
        <PdfPageCanvas
          containerWidth={containerWidth}
          page={page}
          pdfDoc={pdfDoc}
          onRendered={onRendered}
        />
      ) : (
        <div
          className="grid max-w-full place-items-center rounded border border-dashed border-[var(--dc-border)] bg-[linear-gradient(135deg,rgba(248,251,255,0.9),rgba(241,246,252,0.9)),#fff] text-sm font-[760] text-[var(--dc-muted)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.8)]"
          style={{
            height: `${Math.round(containerWidth * 1.42)}px`,
            width: `${containerWidth}px`,
          }}
        >
          <span>p.{page}</span>
        </div>
      )}
    </div>
  );
}

function PdfPageCanvas({
  containerWidth,
  page,
  pdfDoc,
  onRendered,
}: {
  containerWidth: number;
  page: number;
  pdfDoc: PDFDocumentProxy;
  onRendered: (page: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);

  useEffect(() => {
    let destroyed = false;

    async function renderPage() {
      const pdfPage = await pdfDoc.getPage(page);
      const canvas = canvasRef.current;
      if (!canvas || destroyed) {
        return;
      }

      const viewport = pdfPage.getViewport({ scale: 1 });
      const scale = containerWidth / viewport.width;
      const scaledViewport = pdfPage.getViewport({ scale });
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

      renderTaskRef.current = pdfPage.render({
        canvas,
        canvasContext: context,
        viewport: scaledViewport,
      });
      await renderTaskRef.current.promise;
      if (!destroyed) {
        onRendered(page);
      }
    }

    void renderPage();

    return () => {
      destroyed = true;
      renderTaskRef.current?.cancel();
    };
  }, [containerWidth, onRendered, page, pdfDoc]);

  return <canvas ref={canvasRef} data-testid="pdf-canvas" />;
}

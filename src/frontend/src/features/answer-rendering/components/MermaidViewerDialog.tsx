import { useCallback, useRef } from "react";

import { ZoomViewerDialog, type ZoomFitContext } from "./ZoomViewerDialog";

export function MermaidViewerDialog({
  onOpenChange,
  open,
  svg,
}: {
  onOpenChange: (open: boolean) => void;
  open: boolean;
  svg: string;
}) {
  const svgHostRef = useRef<HTMLDivElement | null>(null);

  const fitToView = useCallback((context: ZoomFitContext, animationTime = 180) => {
    const svgElement = svgHostRef.current?.querySelector("svg");
    if (!svgElement) {
      return;
    }

    const svgSize = getSvgIntrinsicSize(svgElement);
    if (!svgSize) {
      return;
    }
    svgElement.style.width = `${svgSize.width}px`;
    svgElement.style.height = `${svgSize.height}px`;

    context.fitContentToView(svgSize, animationTime);
  }, []);

  return (
    <ZoomViewerDialog
      controlsLabel="Mermaid図の表示操作"
      description="Mermaid図を拡大し、マウスホイールとドラッグで表示範囲を操作できます。"
      fitKey={svg}
      fitLabel="Mermaid図全体を表示"
      fitTooltip="図全体を表示"
      onFitToView={fitToView}
      onOpenChange={onOpenChange}
      open={open}
      title="Mermaid図"
      zoomInLabel="Mermaid図を拡大"
      zoomOutLabel="Mermaid図を縮小"
    >
      <div
        className="mermaid-viewer-svg inline-block rounded-xl bg-white p-7 shadow-[0_18px_46px_rgba(25,42,70,0.18)]"
        ref={svgHostRef}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </ZoomViewerDialog>
  );
}

function getSvgIntrinsicSize(svgElement: SVGSVGElement) {
  const viewBox = svgElement.viewBox.baseVal;
  if (viewBox.width > 0 && viewBox.height > 0) {
    return {
      width: viewBox.width,
      height: viewBox.height,
    };
  }

  const width = parseSvgDimension(svgElement.getAttribute("width"));
  const height = parseSvgDimension(svgElement.getAttribute("height"));
  if (width && height) {
    return { width, height };
  }

  const rect = svgElement.getBoundingClientRect();
  if (rect.width > 0 && rect.height > 0) {
    return {
      width: rect.width,
      height: rect.height,
    };
  }

  return null;
}

function parseSvgDimension(value: string | null) {
  if (!value) {
    return null;
  }

  const parsed = Number.parseFloat(value.replace("px", ""));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

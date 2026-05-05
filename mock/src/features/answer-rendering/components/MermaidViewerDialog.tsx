import { Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { TransformComponent, TransformWrapper, useControls } from "react-zoom-pan-pinch";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function MermaidViewerDialog({
  onOpenChange,
  open,
  svg,
}: {
  onOpenChange: (open: boolean) => void;
  open: boolean;
  svg: string;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="mermaid-viewer-dialog gap-0 overflow-hidden p-0" aria-describedby="mermaid-viewer-description">
        <DialogHeader className="mermaid-viewer-header">
          <DialogTitle className="text-xl leading-[1.3] font-bold">Mermaid図</DialogTitle>
          <DialogDescription id="mermaid-viewer-description" className="sr-only">
            Mermaid図を拡大し、マウスホイールとドラッグで表示範囲を操作できます。
          </DialogDescription>
        </DialogHeader>
        <TransformWrapper
          centerOnInit
          doubleClick={{ disabled: true }}
          limitToBounds={false}
          maxScale={4}
          minScale={0.15}
          panning={{ velocityDisabled: true }}
          smooth={false}
          wheel={{ step: 0.08 }}
        >
          <MermaidZoomSurface svg={svg} />
        </TransformWrapper>
      </DialogContent>
    </Dialog>
  );
}

function MermaidZoomSurface({ svg }: { svg: string }) {
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const svgHostRef = useRef<HTMLDivElement | null>(null);
  const { setTransform, zoomIn, zoomOut } = useControls();

  const fitToView = useCallback((animationTime = 180) => {
    const surface = surfaceRef.current;
    const svgElement = svgHostRef.current?.querySelector("svg");
    if (!surface || !svgElement) {
      return;
    }

    const svgSize = getSvgIntrinsicSize(svgElement);
    if (!svgSize) {
      return;
    }
    svgElement.style.width = `${svgSize.width}px`;
    svgElement.style.height = `${svgSize.height}px`;

    const horizontalPadding = 48;
    const verticalPadding = 48;
    const availableWidth = Math.max(120, surface.clientWidth - horizontalPadding);
    const availableHeight = Math.max(120, surface.clientHeight - verticalPadding);
    const scale = Math.min(availableWidth / svgSize.width, availableHeight / svgSize.height, 1);
    const positionX = Math.round((surface.clientWidth - svgSize.width * scale) / 2);
    const positionY = Math.round((surface.clientHeight - svgSize.height * scale) / 2);

    setTransform(positionX, positionY, scale, animationTime, "easeOut");
  }, [setTransform]);

  useEffect(() => {
    const frame = requestAnimationFrame(() => fitToView(0));
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [fitToView, svg]);

  return (
    <div className="mermaid-viewer-body">
      <div className="mermaid-viewer-toolbar" aria-label="Mermaid図の表示操作">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-label="Mermaid図を拡大"
              className="mermaid-viewer-tool-button"
              onClick={() => zoomIn(0.1)}
              size="icon"
              type="button"
              variant="secondary"
            >
              <Plus size={18} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>拡大</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-label="Mermaid図を縮小"
              className="mermaid-viewer-tool-button"
              onClick={() => zoomOut(0.1)}
              size="icon"
              type="button"
              variant="secondary"
            >
              <Minus size={18} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>縮小</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              className="mermaid-viewer-fit-button"
              onClick={() => fitToView()}
              type="button"
              variant="secondary"
            >
              フィット
            </Button>
          </TooltipTrigger>
          <TooltipContent>図全体を表示</TooltipContent>
        </Tooltip>
      </div>
      <div className="mermaid-viewer-surface" ref={surfaceRef}>
        <TransformComponent
          wrapperClass="mermaid-transform-wrapper"
          contentClass="mermaid-transform-content"
        >
          <div
            className="mermaid-viewer-svg"
            ref={svgHostRef}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        </TransformComponent>
      </div>
    </div>
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

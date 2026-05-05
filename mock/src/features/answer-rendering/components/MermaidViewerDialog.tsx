import { Minus, Plus, Scan } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { TransformComponent, TransformWrapper, useControls } from "react-zoom-pan-pinch";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
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
      <DialogContent
        className="!h-[calc(100vh-24px)] !w-[calc(100vw-24px)] !max-w-none grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden bg-[#f7f9fc] p-0"
        aria-describedby="mermaid-viewer-description"
      >
        <header className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-[18px] border-b border-[#dce6f3] bg-white pt-[18px] pr-[18px] pb-[14px] pl-6">
          <DialogHeader>
            <DialogTitle className="text-xl leading-[1.3] font-bold">Mermaid図</DialogTitle>
            <DialogDescription id="mermaid-viewer-description" className="sr-only">
              Mermaid図を拡大し、マウスホイールとドラッグで表示範囲を操作できます。
            </DialogDescription>
          </DialogHeader>
          <DialogClose />
        </header>
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
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        className="absolute top-3.5 right-[18px] z-2 flex gap-2 rounded-[10px] border border-[#d7e1ee] bg-white/95 p-1.5 shadow-[0_16px_34px_rgba(25,42,70,0.14)]"
        aria-label="Mermaid図の表示操作"
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-label="Mermaid図を拡大"
              className="size-[34px] rounded-lg bg-[#eef4fb] text-[#33445f]"
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
              className="size-[34px] rounded-lg bg-[#eef4fb] text-[#33445f]"
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
              aria-label="Mermaid図全体を表示"
              className="size-[34px] rounded-lg bg-[#eef4fb] text-[#33445f]"
              onClick={() => fitToView()}
              size="icon"
              type="button"
              variant="secondary"
            >
              <Scan size={18} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>図全体を表示</TooltipContent>
        </Tooltip>
      </div>
      <div
        className="h-full min-h-0 flex-1 overflow-hidden bg-[linear-gradient(90deg,rgba(148,163,184,0.12)_1px,transparent_1px),linear-gradient(180deg,rgba(148,163,184,0.12)_1px,transparent_1px),#eef3f9] bg-[length:28px_28px]"
        ref={surfaceRef}
      >
        <TransformComponent
          wrapperClass="!h-full !w-full cursor-grab active:cursor-grabbing"
          contentClass="inline-flex items-start justify-start"
        >
          <div
            className="mermaid-viewer-svg inline-block rounded-xl bg-white p-7 shadow-[0_18px_46px_rgba(25,42,70,0.18)]"
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

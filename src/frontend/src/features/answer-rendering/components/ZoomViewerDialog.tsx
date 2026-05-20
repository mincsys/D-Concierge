import { Minus, Plus, Scan } from "lucide-react";
import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { TransformComponent, TransformWrapper, useControls } from "react-zoom-pan-pinch";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type SetTransform = ReturnType<typeof useControls>["setTransform"];

export type ZoomFitContext = {
  fitContentToView: (size: ZoomContentSize, animationTime?: number) => void;
  surface: HTMLDivElement;
};

export type ZoomContentSize = {
  height: number;
  width: number;
};

type ZoomViewerDialogProps = {
  children: ReactNode;
  controlsLabel: string;
  description: string;
  fitKey: string;
  fitLabel: string;
  fitTooltip: string;
  onFitToView: (context: ZoomFitContext, animationTime?: number) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  title: string;
  zoomInLabel: string;
  zoomOutLabel: string;
};

export function ZoomViewerDialog({
  children,
  controlsLabel,
  description,
  fitKey,
  fitLabel,
  fitTooltip,
  onFitToView,
  onOpenChange,
  open,
  title,
  zoomInLabel,
  zoomOutLabel,
}: ZoomViewerDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!h-[calc(100vh-24px)] !w-[calc(100vw-24px)] !max-w-none grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden bg-[var(--dc-panel)] p-0">
        <header className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-[18px] border-b border-[var(--dc-border)] bg-white pt-[18px] pr-[18px] pb-[14px] pl-6">
          <DialogHeader>
            <DialogTitle className="text-xl leading-[1.3] font-bold">{title}</DialogTitle>
            <DialogDescription className="sr-only">{description}</DialogDescription>
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
          <ZoomSurface
            controlsLabel={controlsLabel}
            fitKey={fitKey}
            fitLabel={fitLabel}
            fitTooltip={fitTooltip}
            onFitToView={onFitToView}
            zoomInLabel={zoomInLabel}
            zoomOutLabel={zoomOutLabel}
          >
            {children}
          </ZoomSurface>
        </TransformWrapper>
      </DialogContent>
    </Dialog>
  );
}

function ZoomSurface({
  children,
  controlsLabel,
  fitKey,
  fitLabel,
  fitTooltip,
  onFitToView,
  zoomInLabel,
  zoomOutLabel,
}: Omit<ZoomViewerDialogProps, "description" | "onOpenChange" | "open" | "title">) {
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const { setTransform, zoomIn, zoomOut } = useControls();

  const fitToView = useCallback(
    (animationTime = 180) => {
      const surface = surfaceRef.current;
      if (!surface) {
        return;
      }
      onFitToView(
        {
          fitContentToView: (size, nextAnimationTime = animationTime) =>
            fitContentToView({
              animationTime: nextAnimationTime,
              setTransform,
              size,
              surface,
            }),
          surface,
        },
        animationTime,
      );
    },
    [onFitToView, setTransform],
  );

  useEffect(() => {
    const frame = requestAnimationFrame(() => fitToView(0));
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [fitKey, fitToView]);

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        className="absolute top-3.5 right-[18px] z-2 flex gap-2 rounded-[10px] border border-[var(--dc-border)] bg-white/95 p-1.5 shadow-[0_16px_34px_rgba(25,42,70,0.14)]"
        aria-label={controlsLabel}
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-label={zoomInLabel}
              className="size-[34px] rounded-lg bg-[var(--dc-primary-softer)] text-[var(--dc-muted-strong)]"
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
              aria-label={zoomOutLabel}
              className="size-[34px] rounded-lg bg-[var(--dc-primary-softer)] text-[var(--dc-muted-strong)]"
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
              aria-label={fitLabel}
              className="size-[34px] rounded-lg bg-[var(--dc-primary-softer)] text-[var(--dc-muted-strong)]"
              onClick={() => fitToView()}
              size="icon"
              type="button"
              variant="secondary"
            >
              <Scan size={18} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{fitTooltip}</TooltipContent>
        </Tooltip>
      </div>
      <div
        className="h-full min-h-0 flex-1 overflow-hidden bg-[linear-gradient(90deg,rgba(148,163,184,0.12)_1px,transparent_1px),linear-gradient(180deg,rgba(148,163,184,0.12)_1px,transparent_1px),var(--dc-panel)] bg-[length:28px_28px]"
        ref={surfaceRef}
      >
        <TransformComponent
          wrapperClass="!h-full !w-full cursor-grab active:cursor-grabbing"
          contentClass="inline-flex items-start justify-start"
        >
          {children}
        </TransformComponent>
      </div>
    </div>
  );
}

function fitContentToView({
  animationTime = 180,
  setTransform,
  size,
  surface,
}: {
  animationTime?: number;
  setTransform: SetTransform;
  size: ZoomContentSize;
  surface: HTMLDivElement;
}) {
  const horizontalPadding = 48;
  const verticalPadding = 48;
  const availableWidth = Math.max(120, surface.clientWidth - horizontalPadding);
  const availableHeight = Math.max(120, surface.clientHeight - verticalPadding);
  const scale = Math.min(availableWidth / size.width, availableHeight / size.height, 1);
  const positionX = Math.round((surface.clientWidth - size.width * scale) / 2);
  const positionY = Math.round((surface.clientHeight - size.height * scale) / 2);

  setTransform(positionX, positionY, scale, animationTime, "easeOut");
}

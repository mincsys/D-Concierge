import { useCallback, useEffect, useRef, useState } from "react";

import { ZoomViewerDialog, type ZoomFitContext } from "./ZoomViewerDialog";

export function ImageViewerDialog({
  alt,
  onOpenChange,
  open,
  src,
}: {
  alt: string;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  src: string;
}) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
  }, [src]);

  useEffect(() => {
    const image = imageRef.current;
    if (image?.complete && image.naturalWidth > 0 && image.naturalHeight > 0) {
      setLoaded(true);
    }
  }, [src]);

  const fitToView = useCallback((context: ZoomFitContext, animationTime = 180) => {
    const image = imageRef.current;
    if (!image || image.naturalWidth <= 0 || image.naturalHeight <= 0) {
      return;
    }

    image.style.width = `${image.naturalWidth}px`;
    image.style.height = `${image.naturalHeight}px`;
    context.fitContentToView(
      { height: image.naturalHeight, width: image.naturalWidth },
      animationTime,
    );
  }, []);

  return (
    <ZoomViewerDialog
      controlsLabel="画像の表示操作"
      description="画像を拡大し、マウスホイールとドラッグで表示範囲を操作できます。"
      fitKey={`${src}:${loaded}`}
      fitLabel="画像全体を表示"
      fitTooltip="画像全体を表示"
      onFitToView={fitToView}
      onOpenChange={onOpenChange}
      open={open}
      title="画像"
      zoomInLabel="画像を拡大"
      zoomOutLabel="画像を縮小"
    >
      <img
        alt={alt}
        className="inline-block max-w-none rounded-xl bg-white shadow-[0_18px_46px_rgba(25,42,70,0.18)]"
        ref={imageRef}
        src={src}
        onLoad={() => setLoaded(true)}
      />
    </ZoomViewerDialog>
  );
}

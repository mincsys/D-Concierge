import mermaid from "mermaid";
import { Maximize2 } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { MermaidViewerDialog } from "./MermaidViewerDialog";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "base",
  themeVariables: {
    primaryColor: "#e8f0ff",
    primaryBorderColor: "#0f55ad",
    primaryTextColor: "#132238",
    lineColor: "#7d8aa8",
    fontFamily: "Inter, system-ui, sans-serif",
  },
});

export function MermaidRenderer({ source }: { source: string }) {
  const [svg, setSvg] = useState("");
  const [viewerOpen, setViewerOpen] = useState(false);
  const [renderFailed, setRenderFailed] = useState(false);
  const reactId = useId();
  const renderSequenceRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const safeReactId = reactId.replace(/[^a-zA-Z0-9_-]/g, "");
    const renderId = `mock-flow-${safeReactId}-${renderSequenceRef.current}`;
    renderSequenceRef.current += 1;
    setSvg("");
    setRenderFailed(false);

    mermaid
      .render(renderId, source)
      .then(({ svg: renderedSvg }) => {
        if (!cancelled) {
          setSvg(renderedSvg);
          setRenderFailed(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSvg("");
          setRenderFailed(true);
        }
      })
      .finally(() => {
        removeMermaidInjectedElement(renderId);
      });

    return () => {
      cancelled = true;
    };
  }, [reactId, source]);

  return (
    <div className="group relative overflow-hidden rounded-lg border border-[var(--dc-border)] bg-[var(--dc-sidebar-from)] p-3">
      {svg && !renderFailed ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-label="Mermaid図を拡大表示"
              className="pointer-events-none absolute top-2.5 right-2.5 z-1 size-[34px] rounded-lg border border-[var(--dc-border)] bg-white/90 text-[var(--dc-muted-strong)] opacity-0 shadow-[0_8px_20px_rgba(25,42,70,0.12)] transition-opacity duration-150 hover:bg-white hover:text-[var(--dc-primary)] group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100"
              onClick={() => setViewerOpen(true)}
              size="icon"
              type="button"
              variant="ghost"
            >
              <Maximize2 size={18} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>拡大表示</TooltipContent>
        </Tooltip>
      ) : null}
      {renderFailed ? (
        <pre className="m-0 whitespace-pre-wrap text-sm font-[720] text-[#9f1d1d]">
          Mermaid図を表示できませんでした。
        </pre>
      ) : (
        <div className="mermaid-preview min-h-[120px]" dangerouslySetInnerHTML={{ __html: svg }} />
      )}
      <MermaidViewerDialog open={viewerOpen} onOpenChange={setViewerOpen} svg={svg} />
    </div>
  );
}

function removeMermaidInjectedElement(renderId: string) {
  document.getElementById(renderId)?.remove();
}

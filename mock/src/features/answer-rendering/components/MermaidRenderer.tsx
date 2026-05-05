import mermaid from "mermaid";
import { Maximize2 } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { MermaidViewerDialog } from "./MermaidViewerDialog";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "base",
  themeVariables: {
    primaryColor: "#eaf2ff",
    primaryBorderColor: "#4f8cff",
    primaryTextColor: "#172033",
    lineColor: "#7d8aa8",
    fontFamily: "Inter, system-ui, sans-serif",
  },
});

export function MermaidRenderer({ source }: { source: string }) {
  const [svg, setSvg] = useState("");
  const [viewerOpen, setViewerOpen] = useState(false);
  const [renderFailed, setRenderFailed] = useState(false);
  const reactId = useId();

  useEffect(() => {
    let cancelled = false;
    setSvg("");
    setRenderFailed(false);

    mermaid
      .render(`mock-flow-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`, source)
      .then(({ svg: renderedSvg }) => {
        if (!cancelled) {
          setSvg(renderedSvg);
          setRenderFailed(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSvg('<pre class="mermaid-fallback">Mermaid図を表示できませんでした。</pre>');
          setRenderFailed(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reactId, source]);

  return (
    <div className="mermaid-box">
      {svg && !renderFailed ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-label="Mermaid図を拡大表示"
              className="mermaid-expand-button"
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
      <div className="mermaid-preview" dangerouslySetInnerHTML={{ __html: svg }} />
      <MermaidViewerDialog open={viewerOpen} onOpenChange={setViewerOpen} svg={svg} />
    </div>
  );
}

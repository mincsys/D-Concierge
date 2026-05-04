import mermaid from "mermaid";
import { useEffect, useId, useState } from "react";

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
  const reactId = useId();

  useEffect(() => {
    let cancelled = false;

    mermaid
      .render(`mock-flow-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`, source)
      .then(({ svg: renderedSvg }) => {
        if (!cancelled) {
          setSvg(renderedSvg);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSvg('<pre class="mermaid-fallback">Mermaid図を表示できませんでした。</pre>');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reactId, source]);

  return <div className="mermaid-box" dangerouslySetInnerHTML={{ __html: svg }} />;
}

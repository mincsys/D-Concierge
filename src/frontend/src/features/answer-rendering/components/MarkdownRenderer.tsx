import { useState, type ReactNode } from "react";
import { Check, Copy, Maximize2 } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { PluggableList } from "unified";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { ImageViewerDialog } from "./ImageViewerDialog";
import { MermaidRenderer } from "./MermaidRenderer";

const markdownSanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    /* istanbul ignore next -- rehype-sanitizeの既定schemaはcode属性定義を持つ */
    code: [...(defaultSchema.attributes?.code ?? []), ["className", /^language-./]],
    /* istanbul ignore next -- rehype-sanitizeの既定schemaはimg属性定義を持つ */
    img: [...(defaultSchema.attributes?.img ?? []), "className", "loading", "src", "alt"],
    /* istanbul ignore next -- rehype-sanitizeの既定schemaはtable属性定義を持つ */
    table: [...(defaultSchema.attributes?.table ?? []), "className"],
  },
};

const rehypePlugins: PluggableList = [rehypeRaw, [rehypeSanitize, markdownSanitizeSchema]];

const markdownComponents: Components = {
  a({ children, href }) {
    if (!href) {
      return <>{children}</>;
    }

    return (
      <a href={href} rel="noreferrer" target="_blank">
        {children}
      </a>
    );
  },
  code({ children, className }) {
    const language = /language-(\w+)/.exec(className ?? "")?.[1];
    const rawSource = toText(children);
    const source = rawSource.replace(/\n$/, "");
    const isCodeBlock = Boolean(className) || rawSource.includes("\n");

    if (language === "mermaid") {
      return <MermaidRenderer source={source.trim()} />;
    }

    if (isCodeBlock) {
      return <MarkdownCodeBlock language={language} source={source} />;
    }

    return (
      <code className="rounded-md border border-[var(--dc-border-soft)] bg-[var(--dc-primary-softer)] px-1.5 py-0.5 font-mono text-[0.92em] text-[var(--dc-primary-strong)]">
        {children}
      </code>
    );
  },
  img({ alt, src }) {
    if (!src || !isAllowedArtifactImageSrc(src)) {
      return null;
    }

    return <ArtifactImage alt={alt ?? ""} src={src} />;
  },
  pre({ children }) {
    return <>{children}</>;
  },
};

export function MarkdownRenderer({ markdown }: { markdown: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        components={markdownComponents}
        rehypePlugins={rehypePlugins}
        remarkPlugins={[remarkGfm]}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

function ArtifactImage({ alt, src }: { alt: string; src: string }) {
  const [failed, setFailed] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);

  if (failed) {
    return (
      <span className="my-3 block rounded-lg border border-[#f2b8b8] bg-[#fff6f6] px-4 py-3 text-sm font-[720] text-[#9f1d1d]">
        一部のCodex成果物を表示できませんでした。
      </span>
    );
  }

  return (
    <span className="group relative my-3 block max-w-full">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            aria-label="画像を拡大表示"
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
      <img
        alt={alt}
        className="markdown-image"
        loading="lazy"
        src={src}
        onError={() => setFailed(true)}
      />
      <ImageViewerDialog alt={alt} open={viewerOpen} src={src} onOpenChange={setViewerOpen} />
    </span>
  );
}

function MarkdownCodeBlock({ language, source }: { language?: string; source: string }) {
  const [copied, setCopied] = useState(false);
  const languageLabel = language ?? "text";

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1300);
    } catch {
      setCopied(false);
    }
  }

  return (
    <figure className="my-5 overflow-hidden rounded-xl border border-[#404b59] bg-[#323c49] shadow-[0_12px_32px_rgba(25,42,70,0.18)]">
      <figcaption className="flex min-h-10 items-center justify-between gap-3 border-b border-[#3a4552] bg-[#3f4a58] px-4 py-2">
        <span className="font-mono text-xs font-[760] tracking-normal text-[#edf2f8]">
          {languageLabel}
        </span>
        <button
          className="grid size-7 place-items-center rounded-md bg-transparent text-[#d8dee6] transition-colors hover:bg-[#4a5563] hover:text-[#f8fbff]"
          type="button"
          aria-label={copied ? "コピーしました" : "コードをコピー"}
          onClick={handleCopy}
        >
          {copied ? <Check size={17} /> : <Copy size={17} />}
        </button>
      </figcaption>
      <pre className="m-0 overflow-x-auto bg-[#323c49] px-4 py-3.5 text-[13.5px] leading-6 text-[#d6dce4] [scrollbar-color:#b9bec5_#323c49] [&::-webkit-scrollbar]:h-3 [&::-webkit-scrollbar-track]:bg-[#323c49] [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-[#323c49] [&::-webkit-scrollbar-thumb]:bg-[#b9bec5]">
        <code className="font-mono whitespace-pre">{source}</code>
      </pre>
    </figure>
  );
}

function isAllowedArtifactImageSrc(src: string) {
  try {
    const url = new URL(src, window.location.origin);
    return url.origin === window.location.origin && url.pathname.startsWith("/api/artifacts/");
  } catch {
    return false;
  }
}

function toText(value: ReactNode): string {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map(toText).join("");
  }

  return "";
}

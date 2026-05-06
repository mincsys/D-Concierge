import { useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { PluggableList } from "unified";

import { MermaidRenderer } from "./MermaidRenderer";

const markdownSanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [
      ...(defaultSchema.attributes?.code ?? []),
      ["className", /^language-./],
    ],
    img: [
      ...(defaultSchema.attributes?.img ?? []),
      "className",
      "loading",
      "src",
      "alt",
    ],
    table: [
      ...(defaultSchema.attributes?.table ?? []),
      "className",
    ],
  },
};

const rehypePlugins: PluggableList = [
  rehypeRaw,
  [rehypeSanitize, markdownSanitizeSchema],
];

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

    return <img alt={alt ?? ""} className="markdown-image" loading="lazy" src={src} />;
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
    <figure className="my-5 overflow-hidden rounded-xl border border-[var(--dc-border)] bg-[#edf1f6] shadow-[0_10px_28px_rgba(25,42,70,0.07)]">
      <figcaption className="flex min-h-10 items-center justify-between gap-3 border-b border-[var(--dc-border-soft)] bg-[#e3e9f1] px-4 py-2">
        <span className="font-mono text-xs font-[760] tracking-normal text-[var(--dc-muted-strong)]">
          {languageLabel}
        </span>
        <button
          className="grid size-7 place-items-center rounded-md bg-transparent text-[var(--dc-muted-strong)] transition-colors hover:bg-[#f7f9fc] hover:text-[var(--dc-muted-strong)]"
          type="button"
          aria-label={copied ? "コピーしました" : "コードをコピー"}
          onClick={handleCopy}
        >
          {copied ? <Check size={17} /> : <Copy size={17} />}
        </button>
      </figcaption>
      <pre className="m-0 overflow-x-auto bg-[#edf1f6] px-4 py-3.5 text-[13.5px] leading-6 text-[var(--dc-text)]">
        <code className="font-mono whitespace-pre">{source}</code>
      </pre>
    </figure>
  );
}

function isAllowedArtifactImageSrc(src: string) {
  try {
    const url = new URL(src, window.location.origin);
    return url.origin === window.location.origin && url.pathname.startsWith("/artifacts/");
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

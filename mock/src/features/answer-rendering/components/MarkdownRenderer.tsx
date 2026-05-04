import type { ReactNode } from "react";
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
    const source = toText(children).trim();

    if (language === "mermaid") {
      return <MermaidRenderer source={source} />;
    }

    return <code className={className}>{children}</code>;
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

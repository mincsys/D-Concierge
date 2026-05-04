import { sanitizeHtml } from "@/features/answer-rendering/lib/sanitize";

export function HtmlRenderer({ html }: { html: string }) {
  return (
    <div
      className="table-wrap"
      dangerouslySetInnerHTML={{
        __html: sanitizeHtml(html),
      }}
    />
  );
}

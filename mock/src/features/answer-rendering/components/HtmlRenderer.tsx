import { answerTableHtml } from "@/features/chat/model/fixtures";
import { sanitizeHtml } from "@/features/answer-rendering/lib/sanitize";

export function HtmlRenderer() {
  return (
    <div
      className="table-wrap"
      dangerouslySetInnerHTML={{
        __html: sanitizeHtml(answerTableHtml),
      }}
    />
  );
}

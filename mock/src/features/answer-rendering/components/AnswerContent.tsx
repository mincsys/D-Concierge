import type { ChatAnswer } from "@/features/chat/model/types";
import { ReferenceLink } from "@/features/reference-viewer/components/ReferenceLink";
import { formatPdfPageRange } from "@/features/reference-viewer/lib/pageRange";
import type { PdfReference } from "@/features/reference-viewer/model/types";
import { MarkdownRenderer } from "./MarkdownRenderer";

export function AnswerContent({
  answer,
  onOpenPdf,
}: {
  answer: ChatAnswer;
  onOpenPdf: (reference: PdfReference) => void;
}) {
  return (
    <div className="ml-20 text-[15.5px] leading-[1.72] text-[#172033]">
      {answer.blocks.map((block) => (
        <section className="mt-7 first:mt-0" key={block.id}>
          <MarkdownRenderer markdown={block.markdown} />
          {block.references.length > 0 ? (
            <div className="mt-3 grid gap-1.5" aria-label="参照元">
              {block.references.map((reference) => (
                <ReferenceLink
                  key={reference.id}
                  label={`${reference.title} ${formatPdfPageRange(reference)}`}
                  onClick={() => onOpenPdf(reference)}
                />
              ))}
            </div>
          ) : null}
        </section>
      ))}
    </div>
  );
}

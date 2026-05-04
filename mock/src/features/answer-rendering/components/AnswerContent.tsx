import type { ChatAnswer } from "@/features/chat/model/types";
import { ReferenceLink } from "@/features/reference-viewer/components/ReferenceLink";
import { HtmlRenderer } from "./HtmlRenderer";
import { ImageRenderer } from "./ImageRenderer";
import { MermaidRenderer } from "./MermaidRenderer";

export function AnswerContent({
  answer,
  onOpenPdf,
}: {
  answer: ChatAnswer;
  onOpenPdf: () => void;
}) {
  return (
    <div className="ml-20 text-[15.5px] leading-[1.72] text-[#172033]">
      <p className="mb-3.5 font-[620]">{answer.intro}</p>
      <ol className="mb-[17px] list-decimal pl-[22px]">
        {answer.points.map((point) => (
          <li className="mb-[13px] pl-[9px] font-[620]" key={point.id}>
            <strong className="mb-0.5 block font-[830]">{point.title}</strong>
            <span className="block">{point.description}</span>
            <ReferenceLink onClick={onOpenPdf} label={point.referenceLabel} />
          </li>
        ))}
      </ol>

      <section className="mt-[22px]">
        <h2 className="mb-[11px] text-base font-[830] text-[#16233a]">{answer.workflowTitle}</h2>
        <MermaidRenderer />
      </section>

      <section className="mt-[22px]">
        <h2 className="mb-[11px] text-base font-[830] text-[#16233a]">{answer.imageTitle}</h2>
        <ImageRenderer />
      </section>

      <section className="mt-[22px]">
        <h2 className="mb-[11px] text-base font-[830] text-[#16233a]">{answer.htmlTitle}</h2>
        <HtmlRenderer html={answer.html} />
      </section>

      <p className="mt-5 text-sm text-[#65728c]">{answer.note}</p>
    </div>
  );
}

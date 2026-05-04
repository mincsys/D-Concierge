import { answerPoints } from "@/features/chat/model/fixtures";
import { ReferenceLink } from "@/features/reference-viewer/components/ReferenceLink";
import { HtmlRenderer } from "./HtmlRenderer";
import { ImageRenderer } from "./ImageRenderer";
import { MermaidRenderer } from "./MermaidRenderer";

export function AnswerContent({ onOpenPdf }: { onOpenPdf: () => void }) {
  return (
    <div className="ml-20 text-[15.5px] leading-[1.72] text-[#172033]">
      <p className="mb-3.5 font-[620]">
        IPA資料から、要件定義を成功させるためのポイントを以下の通り整理します。
      </p>
      <ol className="mb-[17px] list-decimal pl-[22px]">
        {answerPoints.map((point) => (
          <li className="mb-[13px] pl-[9px] font-[620]" key={point.title}>
            <strong className="mb-0.5 block font-[830]">{point.title}</strong>
            <span className="block">{point.description}</span>
            <ReferenceLink onClick={onOpenPdf} label={point.referenceLabel} />
          </li>
        ))}
      </ol>

      <section className="mt-[22px]">
        <h2 className="mb-[11px] text-base font-[830] text-[#16233a]">要件定義ワークフロー</h2>
        <MermaidRenderer />
      </section>

      <section className="mt-[22px]">
        <h2 className="mb-[11px] text-base font-[830] text-[#16233a]">分析イメージ</h2>
        <ImageRenderer />
      </section>

      <section className="mt-[22px]">
        <h2 className="mb-[11px] text-base font-[830] text-[#16233a]">HTML表の表示例</h2>
        <HtmlRenderer />
      </section>

      <p className="mt-5 text-sm text-[#65728c]">
        ※ 上記はIPA公開資料をもとに作成した要約です。詳細は参照元PDFをご確認ください。
      </p>
    </div>
  );
}

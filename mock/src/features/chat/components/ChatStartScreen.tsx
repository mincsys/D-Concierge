import { FileText, ListChecks, Search, Split } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ChatComposer } from "./ChatComposer";

const suggestions = [
  { label: "IPA資料の要点を教えて", icon: FileText },
  { label: "要件定義の型どころを整理して", icon: ListChecks },
  { label: "SEC BOOKSを検索して", icon: Search },
  { label: "PDFの参照元を明示して比較して", icon: Split },
];

export function ChatStartScreen({ onStart }: { onStart: () => void }) {
  return (
    <section className="grid min-h-screen place-items-center px-12">
      <div className="w-full translate-y-[-12px]">
        <h1 className="mb-8 text-center text-[25px] font-[780] tracking-normal">
          今日は何をお手伝いできますか？
        </h1>
        <ChatComposer
          className="mx-auto w-[calc(100vw-420px)] max-[1280px]:w-[calc(100vw-390px)]"
          placeholder="質問を入力してください"
          onFocus={onStart}
          onSubmit={() => onStart()}
        />
        <div className="mt-[34px] flex flex-wrap justify-center gap-4">
          {suggestions.map(({ label, icon: Icon }) => (
            <Button
              className="h-[54px] gap-3 rounded-[27px] border border-[#dde5f0] bg-white px-5 text-base font-bold text-[#1e2b43] shadow-[0_9px_22px_rgba(23,36,61,0.03)] hover:bg-white [&_svg]:text-[#0a6cff]"
              key={label}
              type="button"
              variant="outline"
              onClick={onStart}
            >
              <Icon size={22} />
              {label}
            </Button>
          ))}
        </div>
      </div>
    </section>
  );
}

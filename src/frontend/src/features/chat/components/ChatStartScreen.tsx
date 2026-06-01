import { FileText, ListChecks, Search, Split } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ChatComposer } from "./ChatComposer";

const suggestionIcons = [FileText, ListChecks, Search, Split];

export function ChatStartScreen({
  inputSuggestions,
  onStart,
  subWelcomeMessage,
  welcomeMessage,
}: {
  inputSuggestions: string[];
  onStart: (message: string) => void;
  subWelcomeMessage?: string;
  welcomeMessage?: string;
}) {
  const [message, setMessage] = useState("");
  const [focusSignal, setFocusSignal] = useState(0);

  function handleSuggestionClick(label: string) {
    setMessage(label);
    setFocusSignal((current) => current + 1);
  }

  return (
    <section className="grid min-h-screen min-w-0 place-items-center overflow-hidden px-12">
      <div className="w-full max-w-[1040px] translate-y-[-12px]">
        {welcomeMessage || subWelcomeMessage ? (
          <div className="mb-5 text-center">
            {welcomeMessage ? (
              <h1 className="text-[25px] leading-9 font-[780] tracking-normal whitespace-pre-line text-[var(--dc-primary-strong)]">
                {welcomeMessage}
              </h1>
            ) : null}
            {subWelcomeMessage ? (
              <p className="mt-5 text-[20px] leading-8 font-normal tracking-normal whitespace-pre-line text-[var(--dc-text)]">
                {subWelcomeMessage}
              </p>
            ) : null}
          </div>
        ) : null}
        <ChatComposer
          autoFocus
          className="mx-auto w-full"
          focusSignal={focusSignal}
          value={message}
          onValueChange={setMessage}
          onSubmit={onStart}
        />
        {inputSuggestions.length > 0 ? (
          <div className="mt-[34px] flex flex-wrap justify-center gap-4">
            {inputSuggestions.map((label, index) => {
              const Icon = suggestionIcons[index % suggestionIcons.length];

              return (
                <Button
                  className="h-auto min-h-[54px] gap-3 rounded-[27px] border border-[var(--dc-border)] bg-white px-5 py-3 text-center text-base leading-6 font-bold whitespace-pre-line text-[var(--dc-text)] shadow-[0_9px_22px_rgba(23,36,61,0.03)] hover:bg-white [&_svg]:text-[var(--dc-primary)]"
                  key={label}
                  type="button"
                  variant="outline"
                  onClick={() => handleSuggestionClick(label)}
                >
                  <Icon size={22} />
                  {label}
                </Button>
              );
            })}
          </div>
        ) : null}
      </div>
    </section>
  );
}

import type { ReactNode } from "react";

const brandLogoUrl = new URL("../../../assets/d-concierge-logo.png", import.meta.url).href;

export function AuthLayout({ children, title }: { children: ReactNode; title: string }) {
  return (
    <main className="grid min-h-screen place-items-center bg-[var(--dc-app-bg)] px-6 py-10">
      <section className="w-full max-w-[420px] rounded-lg border border-[var(--dc-border)] bg-white px-8 py-7 shadow-[0_18px_48px_rgba(25,42,70,0.12)]">
        <div className="mb-7 flex items-center justify-center gap-3">
          <img className="h-10 w-auto" src={brandLogoUrl} alt="" />
          <div className="text-[25px] leading-none font-extrabold text-[var(--dc-primary-strong)]">
            D-Concierge
          </div>
        </div>
        <h1 className="mb-6 text-center text-xl font-[780] text-[var(--dc-text-strong)]">
          {title}
        </h1>
        {children}
      </section>
    </main>
  );
}

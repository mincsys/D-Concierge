import DOMPurify from "dompurify";
import {
  AlignJustify,
  Bot,
  ChevronDown,
  CircleUserRound,
  FileText,
  ListChecks,
  Mic,
  MoreHorizontal,
  Paperclip,
  Search,
  Send,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Split,
  X,
} from "lucide-react";
import mermaid from "mermaid";
import { useEffect, useMemo, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

type ViewMode = "start" | "answer";

const histories = [
  "要件定義を成功させるポイント",
  "IPA刊行物QA",
  "要件定義の肝どころ",
  "SEC BOOKS 構成検索",
  "PDF相関リンク設計",
  "Codex exec JSON設計",
  "Agentic Search比較",
  "システム化計画の進め方",
  "非機能要件の整理方法",
  "開発プロセス選定ガイド",
  "テスト観点の洗い出し",
  "RFP作成のチェックリスト",
];

const thoughtLines = [
  "検索キーワードを整理します。",
  "関連資料を検索します。",
  "各資料の要点・要約から該当箇所を特定します。",
  "構造化HTML編集を実行します。",
  "quotes表（キーワード一致）を実行します。",
  "要約・参照元の生成を行います。",
];

const sanitizedHtml = DOMPurify.sanitize(`
  <table class="answer-table">
    <thead>
      <tr>
        <th>成功ポイント</th>
        <th>要件定義での意味</th>
        <th>参照元</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>目的共有</td>
        <td>関係者が同じゴールを見て判断できる状態を作る。</td>
        <td>PDF p.10</td>
      </tr>
      <tr>
        <td>要求の具体化</td>
        <td>利用者の業務課題を、検証可能な要求に落とし込む。</td>
        <td>PDF p.10</td>
      </tr>
      <tr>
        <td>継続的な見直し</td>
        <td>環境変化に合わせて、要求と合意内容を更新する。</td>
        <td>PDF p.10</td>
      </tr>
    </tbody>
  </table>
`);

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "base",
  themeVariables: {
    primaryColor: "#eaf2ff",
    primaryBorderColor: "#4f8cff",
    primaryTextColor: "#172033",
    lineColor: "#7d8aa8",
    fontFamily: "Inter, system-ui, sans-serif",
  },
});

function App() {
  const [mode, setMode] = useState<ViewMode>("start");
  const [thoughtOpen, setThoughtOpen] = useState(true);
  const [pdfOpen, setPdfOpen] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar onOpenAnswer={() => setMode("answer")} />
      <main className="main-panel">
        <button className="top-menu" type="button" aria-label="その他">
          <MoreHorizontal size={24} />
        </button>
        {mode === "start" ? (
          <StartScreen onStart={() => setMode("answer")} />
        ) : (
          <AnswerScreen
            thoughtOpen={thoughtOpen}
            onToggleThought={() => setThoughtOpen((current) => !current)}
            onOpenPdf={() => setPdfOpen(true)}
          />
        )}
      </main>
      {pdfOpen ? <PdfModal onClose={() => setPdfOpen(false)} /> : null}
    </div>
  );
}

function Sidebar({ onOpenAnswer }: { onOpenAnswer: () => void }) {
  return (
    <aside className="sidebar">
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true">
          <span />
        </div>
        <div className="brand-name">D-Concierge</div>
        <button className="sidebar-toggle" type="button" aria-label="サイドバー切替">
          <Split size={21} />
        </button>
      </div>
      <button className="new-chat" type="button">
        <span className="plus">+</span>
        新しいチャット
      </button>
      <label className="search-box">
        <Search size={20} />
        <input aria-label="チャットを検索" placeholder="チャットを検索" />
        <kbd>⌘K</kbd>
      </label>
      <div className="history-title">最近のチャット</div>
      <nav className="history-list" aria-label="最近のチャット">
        {histories.map((item, index) => (
          <button
            className={`history-item ${index === 0 ? "active" : ""}`}
            key={item}
            type="button"
            onClick={onOpenAnswer}
          >
            {item}
          </button>
        ))}
      </nav>
      <div className="account-row">
        <div className="avatar">A</div>
        <span>山田 太郎</span>
        <button type="button" aria-label="設定">
          <Settings size={21} />
        </button>
      </div>
    </aside>
  );
}

function StartScreen({ onStart }: { onStart: () => void }) {
  return (
    <section className="start-screen">
      <div className="start-content">
        <h1>今日は何をお手伝いできますか？</h1>
        <div className="hero-input">
          <Paperclip size={24} />
          <input placeholder="質問を入力してください" onFocus={onStart} />
          <button className="ghost-icon" type="button" aria-label="音声入力">
            <Mic size={23} />
          </button>
          <button className="voice-button" type="button" aria-label="開始" onClick={onStart}>
            <AlignJustify size={25} />
          </button>
        </div>
        <div className="suggestions">
          <button type="button" onClick={onStart}>
            <FileText size={22} />
            IPA資料の要点を教えて
          </button>
          <button type="button" onClick={onStart}>
            <ListChecks size={22} />
            要件定義の型どころを整理して
          </button>
          <button type="button" onClick={onStart}>
            <Search size={22} />
            SEC BOOKSを検索して
          </button>
          <button type="button" onClick={onStart}>
            <Split size={22} />
            PDFの参照元を明示して比較して
          </button>
        </div>
      </div>
    </section>
  );
}

function AnswerScreen({
  thoughtOpen,
  onToggleThought,
  onOpenPdf,
}: {
  thoughtOpen: boolean;
  onToggleThought: () => void;
  onOpenPdf: () => void;
}) {
  return (
    <section className="answer-screen">
      <div className="message user-message">要件定義を成功させるポイントをIPA資料から整理して</div>
      <article className="answer-thread">
        <div className="thought-shell">
          <button className="thought-header" type="button" onClick={onToggleThought}>
            <span className="sparkle-badge">
              <Sparkles size={22} fill="#0d64ff" />
            </span>
            <ChevronDown className={thoughtOpen ? "chevron open" : "chevron"} size={19} />
            <span>Thought for 16s</span>
          </button>
          {thoughtOpen ? (
            <div className="thought-body">
              {thoughtLines.map((line) => (
                <div key={line}>{line}</div>
              ))}
            </div>
          ) : null}
        </div>
        <div className="answer-content">
          <p>IPA資料から、要件定義を成功させるためのポイントを以下の通り整理します。</p>
          <ol className="answer-list">
            <li>
              <strong>目的・背景の共有と合意形成を徹底する。</strong>
              <span>要件定義では目的や背景を共有し、関係する組織や役割を明確にすることが合意形成の第一歩です。</span>
              <ReferenceButton onClick={onOpenPdf} label="SEC BOOKS 開発指針手引き p.10" />
            </li>
            <li>
              <strong>利用者視点で要求を具体化する。</strong>
              <span>利用者の業務や課題を深く理解し、価値につながる要求として具体化します。</span>
              <ReferenceButton onClick={onOpenPdf} label="SEC BOOKS 開発指針手引き p.10" />
            </li>
            <li>
              <strong>要求の優先順位付けとスコープ調整を行う。</strong>
              <span>すべての要求を実装するのではなく、ビジネス価値と実現性のバランスで優先順位を付けます。</span>
              <ReferenceButton onClick={onOpenPdf} label="SEC BOOKS 開発指針手引き p.10" />
            </li>
          </ol>

          <section className="render-block">
            <h2>要件定義ワークフロー</h2>
            <MermaidChart />
          </section>

          <section className="render-block">
            <h2>分析イメージ</h2>
            <InsightImage />
          </section>

          <section className="render-block">
            <h2>HTML表の表示例</h2>
            <div className="table-wrap" dangerouslySetInnerHTML={{ __html: sanitizedHtml }} />
          </section>

          <p className="note">
            ※ 上記はIPA公開資料をもとに作成した要約です。詳細は参照元PDFをご確認ください。
          </p>
        </div>
      </article>
      <Composer compact />
    </section>
  );
}

function ReferenceButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button className="reference-link" type="button" onClick={onClick}>
      {label}
    </button>
  );
}

function MermaidChart() {
  const [svg, setSvg] = useState("");

  useEffect(() => {
    let cancelled = false;
    const source = `
      flowchart LR
        A["質問"] --> B["検索"]
        B --> C["分析"]
        C --> D["参照元検証"]
        D --> E["回答"]
    `;

    mermaid
      .render(`mock-flow-${Date.now()}`, source)
      .then(({ svg: renderedSvg }) => {
        if (!cancelled) {
          setSvg(renderedSvg);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSvg('<pre class="mermaid-fallback">Mermaid図を表示できませんでした。</pre>');
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return <div className="mermaid-box" dangerouslySetInnerHTML={{ __html: svg }} />;
}

function InsightImage() {
  return (
    <figure className="insight-image">
      <svg viewBox="0 0 720 250" role="img" aria-label="資料検索と参照元確認の分析イメージ">
        <defs>
          <linearGradient id="insightGradient" x1="0" x2="1">
            <stop offset="0" stopColor="#dbeafe" />
            <stop offset="1" stopColor="#e0f2fe" />
          </linearGradient>
        </defs>
        <rect width="720" height="250" rx="18" fill="url(#insightGradient)" />
        <rect x="42" y="42" width="174" height="166" rx="14" fill="#fff" stroke="#b9c9ee" />
        <rect x="272" y="42" width="176" height="166" rx="14" fill="#fff" stroke="#b9c9ee" />
        <rect x="504" y="42" width="174" height="166" rx="14" fill="#fff" stroke="#b9c9ee" />
        <text x="129" y="82" textAnchor="middle" fill="#1d355d" fontSize="20" fontWeight="700">
          質問
        </text>
        <text x="360" y="82" textAnchor="middle" fill="#1d355d" fontSize="20" fontWeight="700">
          検索・分析
        </text>
        <text x="591" y="82" textAnchor="middle" fill="#1d355d" fontSize="20" fontWeight="700">
          参照元確認
        </text>
        <path d="M225 125 H260" stroke="#2563eb" strokeWidth="5" strokeLinecap="round" />
        <path d="M456 125 H491" stroke="#2563eb" strokeWidth="5" strokeLinecap="round" />
        <circle cx="129" cy="137" r="34" fill="#eef5ff" stroke="#72a7ff" />
        <path d="M112 137h34M129 120v34" stroke="#2563eb" strokeWidth="5" strokeLinecap="round" />
        <path d="M326 135l23 23 46-62" fill="none" stroke="#22a06b" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M558 152l20-52 42 0 20 52z" fill="#eaf2ff" stroke="#2563eb" strokeWidth="5" strokeLinejoin="round" />
      </svg>
      <figcaption>検索結果を分析し、回答と参照元の対応を確認する流れ</figcaption>
    </figure>
  );
}

function Composer({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? "composer compact" : "composer"}>
      <Paperclip size={23} />
      <input placeholder="質問を入力してください（例：資料の要点を教えて、比較表を作って、など）" />
      <button className="composer-tool" type="button" aria-label="表示設定">
        <SlidersHorizontal size={24} />
      </button>
      <button className="send-button" type="button" aria-label="送信">
        <Send size={22} fill="currentColor" />
      </button>
    </div>
  );
}

function PdfModal({ onClose }: { onClose: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const [status, setStatus] = useState("PDF p.10を読み込んでいます。");

  useEffect(() => {
    let destroyed = false;
    let pdfDoc: PDFDocumentProxy | null = null;

    async function renderPdf() {
      try {
        const loadingTask = pdfjsLib.getDocument("/reference-pdf/iot-guide.pdf");
        pdfDoc = await loadingTask.promise;
        const page = await pdfDoc.getPage(10);
        const canvas = canvasRef.current;
        if (!canvas || destroyed) {
          return;
        }

        const containerWidth = Math.min(850, Math.max(620, canvas.parentElement?.clientWidth ?? 760));
        const viewport = page.getViewport({ scale: 1 });
        const scale = containerWidth / viewport.width;
        const scaledViewport = page.getViewport({ scale });
        const pixelRatio = window.devicePixelRatio || 1;
        const context = canvas.getContext("2d");
        if (!context) {
          throw new Error("Canvas contextを取得できません。");
        }

        canvas.width = Math.floor(scaledViewport.width * pixelRatio);
        canvas.height = Math.floor(scaledViewport.height * pixelRatio);
        canvas.style.width = `${Math.floor(scaledViewport.width)}px`;
        canvas.style.height = `${Math.floor(scaledViewport.height)}px`;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

        renderTaskRef.current = page.render({ canvas, canvasContext: context, viewport: scaledViewport });
        await renderTaskRef.current.promise;
        if (!destroyed) {
          setStatus("SEC BOOKS：「つながる世界の開発指針」の実践に向けた手引き PDF p.10");
        }
      } catch (error) {
        if (!destroyed) {
          setStatus(error instanceof Error ? error.message : "PDFを表示できませんでした。");
        }
      }
    }

    void renderPdf();

    return () => {
      destroyed = true;
      renderTaskRef.current?.cancel();
      pdfDoc?.destroy();
    };
  }, []);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="参照元PDF">
      <div className="pdf-modal">
        <header>
          <div>
            <span className="modal-kicker">参照元PDF</span>
            <h2>SEC BOOKS 開発指針手引き</h2>
            <p>{status}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="閉じる">
            <X size={24} />
          </button>
        </header>
        <div className="pdf-canvas-wrap">
          <canvas ref={canvasRef} data-testid="pdf-canvas" />
        </div>
      </div>
    </div>
  );
}

export default App;

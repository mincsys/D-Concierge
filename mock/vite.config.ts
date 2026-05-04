import { createReadStream, existsSync } from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import type { Connect } from "vite";
import { defineConfig } from "vite";

const pdfPath = path.resolve(
  __dirname,
  "../codex/work/raw/pdf/SEC BOOKS：「つながる世界の開発指針」の実践に向けた手引き［IoT高信頼化機能編］.pdf",
);

function serveReferencePdf(): Connect.NextHandleFunction {
  return (req, res, next) => {
    const url = req.url?.split("?")[0];
    if (url !== "/reference-pdf/iot-guide.pdf") {
      next();
      return;
    }

    if (!existsSync(pdfPath)) {
      res.statusCode = 404;
      res.end("reference PDF not found");
      return;
    }

    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Cache-Control", "no-store");
    createReadStream(pdfPath).pipe(res);
  };
}

export default defineConfig({
  plugins: [
    react(),
    {
      name: "serve-reference-pdf",
      configureServer(server) {
        server.middlewares.use(serveReferencePdf());
      },
      configurePreviewServer(server) {
        server.middlewares.use(serveReferencePdf());
      },
    },
  ],
  server: {
    port: 5173,
    strictPort: false,
  },
  preview: {
    port: 4173,
    strictPort: false,
  },
});

import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const isIntegrationSuite = process.env.VITEST_SUITE === "integration";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/support/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["json-summary"],
      reportsDirectory: "coverage",
      include: isIntegrationSuite ? ["src/pages/chat/ChatPage.tsx"] : ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/components/ui/**",
        "src/**/*.d.ts",
        // PDF.jsとcanvasの描画ライフサイクルは単体カバレッジ計測対象外とする。
        "src/features/reference-viewer/viewers/PdfPageViewer.tsx",
      ],
    },
  },
});

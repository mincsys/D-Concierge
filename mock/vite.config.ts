import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import type { ViteDevServer } from "vite";

import { createBackendMockMiddleware } from "./backend_mock/server/middleware";

const backendTarget = process.env.VITE_BACKEND_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig(({ mode }) => {
  const useBackendMock = mode === "mock";

  return {
    build: {
      assetsInlineLimit: 0,
    },
    plugins: [
      react(),
      tailwindcss(),
      ...(useBackendMock
        ? [
            {
              name: "backend-mock",
              configureServer(server: ViteDevServer) {
                server.middlewares.use(
                  createBackendMockMiddleware(path.resolve(__dirname, "./backend_mock")),
                );
              },
            },
          ]
        : []),
    ],
    server: {
      port: 5173,
      strictPort: false,
      proxy: useBackendMock
        ? undefined
        : {
            "/api": {
              target: backendTarget,
              changeOrigin: true,
            },
          },
    },
    preview: {
      port: 4173,
      strictPort: false,
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  };
});

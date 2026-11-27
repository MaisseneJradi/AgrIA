/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";
import { defineConfig } from "vite";

// The API routes of FastAPI (src/api/main.py). In development Vite forwards them to the API: same origin for the
// browser, no CORS. In production FastAPI serves the build itself (AGRIA_UI=react, see README.md).
const API = process.env.AGRIA_API ?? "http://127.0.0.1:8000";
const API_ROUTES = ["/identify", "/diagnose", "/feedback", "/cultures", "/gouvernorats", "/health", "/openapi.json"];

export default defineConfig({
  plugins: [
    react(),
    // bundle report: dist/../stats.html (sizes gzipped), one per build
    visualizer({ filename: "stats.html", gzipSize: true, brotliSize: false, template: "treemap" }),
  ],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    proxy: Object.fromEntries(API_ROUTES.map((r) => [r, { target: API, changeOrigin: false }])),
  },
  build: { target: "es2020", sourcemap: false, assetsInlineLimit: 0 },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});

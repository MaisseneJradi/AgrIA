/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// The API routes of FastAPI (src/api/main.py). In development Vite forwards them to the API: same origin for the
// browser, no CORS. In production FastAPI serves the build itself (AGRIA_UI=react, see README.md).
const API = process.env.AGRIA_API ?? "http://127.0.0.1:8000";
const API_ROUTES = [
  "/identify",
  "/diagnose",
  "/feedback",
  "/cultures",
  "/gouvernorats",
  "/health",
  "/openapi.json",
  "/admin/journal",
];

export default defineConfig({
  plugins: [
    react(),
    // Installable app. The service worker keeps the app shell, the fonts and the two lists (crops, governorates):
    // the app opens without network. The answers of the API are NEVER cached (POST /identify, /diagnose, /feedback
    // and every other route go to the network): an old diagnosis is never shown as new.
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: false,
      includeAssets: ["favicon.svg", "apple-touch-icon.png"],
      manifest: {
        name: "AgrIA – le médecin des plantes",
        short_name: "AgrIA",
        description: "Diagnostic des plantes et produits homologués en Tunisie, en français ou en arabe.",
        lang: "fr",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        background_color: "#F3EFE2",
        theme_color: "#12261B",
        icons: [
          { src: "pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512.png", sizes: "512x512", type: "image/png" },
          { src: "pwa-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        globIgnores: ["**/*vietnamese*"], // fonts for Vietnamese: never needed here
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [
          /^\/(identify|diagnose|feedback|cultures|gouvernorats|health|admin\/journal|docs|openapi)/,
        ],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname === "/cultures" || url.pathname === "/gouvernorats",
            handler: "StaleWhileRevalidate",
            options: { cacheName: "agria-listes", expiration: { maxEntries: 4 } },
          },
        ],
      },
    }),
    // bundle report: stats.html (sizes gzipped), one per build
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

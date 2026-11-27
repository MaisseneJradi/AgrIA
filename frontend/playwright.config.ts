import { defineConfig, devices } from "@playwright/test";

// End-to-end tests on the production build (vite preview), with the Chrome installed on the computer (channel
// "chrome": no browser to download). Phone viewport by default.
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    channel: "chrome",
    ...devices["Pixel 5"],
    viewport: { width: 360, height: 800 },
  },
  webServer: {
    command: "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: true,
  },
});

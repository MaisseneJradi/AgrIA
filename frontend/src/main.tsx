// Self-hosted fonts (no request to Google Fonts): each file is downloaded by the browser only for the characters of
// the page (unicode-range), so a French page never loads the Arabic font and the reverse.
import "@fontsource-variable/dm-sans/wght.css";
import "@fontsource-variable/fraunces/wght.css";
import "@fontsource/noto-naskh-arabic/arabic-400.css";
import "@fontsource/noto-naskh-arabic/arabic-700.css";
import "./styles/index.css";
import "./lib/i18n";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { applyTheme, savedTheme } from "./lib/theme";

applyTheme(savedTheme());
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => applyTheme(savedTheme()));

const root = document.getElementById("root");
if (!root) throw new Error("#root missing in index.html");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

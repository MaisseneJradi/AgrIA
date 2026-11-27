import type { Config } from "tailwindcss";

// Design tokens: every colour is a CSS variable (src/styles/tokens.css) with a light and a dark value, so the
// components only use semantic names (bg, surface, text, primary, warning...). Palette of the presentation:
// deep green #12261B, cream #F3EFE2, leaf green #A8D672, amber #E9A23B, terracotta #E07A5F.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        "surface-2": token("surface-2"),
        text: token("text"),
        muted: token("muted"),
        border: token("border"),
        primary: token("primary"),
        "on-primary": token("on-primary"),
        accent: token("accent"),
        "on-accent": token("on-accent"),
        focus: token("focus"),
        info: { DEFAULT: token("info-fg"), bg: token("info-bg") },
        success: { DEFAULT: token("success-fg"), bg: token("success-bg") },
        warning: { DEFAULT: token("warning-fg"), bg: token("warning-bg"), strong: token("amber") },
        danger: { DEFAULT: token("danger-fg"), bg: token("danger-bg"), strong: token("terracotta") },
        brand: { green: "#12261B", cream: "#F3EFE2", leaf: "#A8D672", amber: "#E9A23B", terracotta: "#E07A5F" },
      },
      fontFamily: {
        display: ['"Fraunces Variable"', "Georgia", "serif"],
        sans: ['"DM Sans Variable"', "system-ui", "sans-serif"],
        arabic: ['"Noto Naskh Arabic"', "Tahoma", "sans-serif"],
      },
      fontSize: { base: ["1rem", { lineHeight: "1.6" }] },
      minHeight: { touch: "3rem" },
      minWidth: { touch: "3rem" },
      borderRadius: { card: "1.25rem" },
      boxShadow: { card: "0 1px 2px rgb(0 0 0 / .06), 0 4px 16px rgb(0 0 0 / .06)" },
      keyframes: {
        "sheet-in": { from: { transform: "translateY(100%)" }, to: { transform: "translateY(0)" } },
        "toast-in": { from: { opacity: "0", transform: "translateY(.5rem)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: { "sheet-in": "sheet-in .2s ease-out", "toast-in": "toast-in .2s ease-out" },
    },
  },
  plugins: [],
} satisfies Config;

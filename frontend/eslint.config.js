import js from "@eslint/js";
import i18next from "eslint-plugin-i18next";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "stats.html", "src/api/schema.d.ts", "playwright-report", "test-results"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strict],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh, i18next },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // every text a farmer reads lives in src/locales/fr.json and ar.json: no raw text in JSX
      "i18next/no-literal-string": ["error", { mode: "jsx-text-only" }],
    },
  },
  {
    // tests and the style guide's technical labels may hold raw text
    files: ["**/*.test.{ts,tsx}", "src/test/**", "tests/**", "src/pages/Styleguide.tsx"],
    rules: { "i18next/no-literal-string": "off" },
  },
);

import { Leaf } from "lucide-react";
import { Link, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LanguageSwitch, ThemeSwitch } from "@/components/ui";

/** Header (name, language always visible, theme), the page, the reminder about the CRDA. */
export function Layout() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:p-3"
      >
        {t("app.skip")}
      </a>
      <header className="sticky top-0 z-30 bg-primary text-on-primary">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-2">
          <Link to="/" className="flex min-h-touch flex-1 items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-accent text-on-accent">
              <Leaf className="size-6" aria-hidden="true" />
            </span>
            <span>
              <span className="block font-display text-xl font-bold leading-none">{t("app.name")}</span>
              <span className="block text-sm opacity-90">{t("app.tagline")}</span>
            </span>
          </Link>
          <LanguageSwitch className="text-text" />
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-3xl space-y-3 px-4 pb-8 text-center text-sm text-muted">
        <p>{t("app.footer")}</p>
        <ThemeSwitch />
      </footer>
    </div>
  );
}

import { FlaskConical, History, Info, Leaf } from "lucide-react";
import { Link, Outlet } from "react-router-dom";
import { useHealth } from "@/api/queries";
import { QueueSender } from "@/features/queue/QueueSender";
import { useTranslation } from "react-i18next";
import { Alert, LanguageSwitch, ThemeSwitch } from "@/components/ui";
import { useOnline } from "@/lib/useOnline";

/** Header (name, language always visible, theme), the page, the reminder about the CRDA. */
export function Layout() {
  const { t } = useTranslation();
  const online = useOnline();
  const health = useHealth();
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:p-3"
      >
        {t("app.skip")}
      </a>
      <QueueSender />
      <header className="sticky top-0 z-30 bg-primary text-on-primary print:static print:bg-transparent print:text-text">
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
          <LanguageSwitch className="text-text print:hidden" />
        </div>
      </header>
      {health.data?.mode_test && (
        <div role="status" className="bg-warning-bg text-warning print:hidden">
          <p className="mx-auto flex max-w-3xl items-center gap-2 px-4 py-2 font-semibold">
            <FlaskConical className="size-5 shrink-0" aria-hidden="true" />
            {t("test.banner")}
          </p>
        </div>
      )}
      <main id="main" className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
        {!online && (
          <Alert tone="danger" className="mb-4">
            {t("net.offline")}
          </Alert>
        )}
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-3xl space-y-3 px-4 pb-32 text-center text-sm text-muted print:pb-0">
        <nav aria-label={t("nav.menu")} className="flex flex-wrap justify-center gap-2 print:hidden">
          <Link
            to="/historique"
            className="inline-flex min-h-touch items-center gap-2 rounded-xl px-3 font-semibold text-text hover:bg-surface-2"
          >
            <History className="size-5" aria-hidden="true" />
            {t("nav.history")}
          </Link>
          <Link
            to="/a-propos"
            className="inline-flex min-h-touch items-center gap-2 rounded-xl px-3 font-semibold text-text hover:bg-surface-2"
          >
            <Info className="size-5" aria-hidden="true" />
            {t("nav.about")}
          </Link>
        </nav>
        <p>{t("app.footer")}</p>
        <ThemeSwitch className="print:hidden" />
      </footer>
    </div>
  );
}

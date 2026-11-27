import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";
import { LANGUAGES, setLang, type Lang } from "@/lib/i18n";

/** FR / ع, always visible: changes the language and the direction of the whole page, kept on the device. */
export function LanguageSwitch({ className }: { className?: string }) {
  const { t, i18n } = useTranslation();
  const current = i18n.language as Lang;
  return (
    <div
      role="group"
      aria-label={t("language.label")}
      className={cn("inline-flex rounded-full bg-surface-2 p-1", className)}
    >
      {LANGUAGES.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={current === l}
          onClick={() => void setLang(l)}
          className={cn(
            "min-h-touch min-w-touch rounded-full px-3 text-base font-bold",
            current === l ? "bg-primary text-on-primary" : "text-text",
          )}
        >
          {/* the accessible name holds the visible text (WCAG 2.5.3): "FR (Français)" */}
          {t(`language.${l}Short`)}
          <span className="sr-only"> ({t(`language.${l}`)})</span>
        </button>
      ))}
    </div>
  );
}

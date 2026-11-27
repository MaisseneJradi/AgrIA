import type { Lang } from "./i18n";

/** A date as the farmer reads it: "27 nov. 2026, 18:20" / "27 نوفمبر 2026، 18:20" (Latin digits, as in Tunisia). */
export function formatDate(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(lang === "ar" ? "ar-TN-u-nu-latn" : "fr-TN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

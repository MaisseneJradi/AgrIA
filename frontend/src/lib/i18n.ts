// FR / AR. The language is kept on the device (same key as the first app: the farmer keeps his choice) and sets
// lang and dir on <html>, so the whole page (Tailwind logical properties ms-/me-/ps-/pe-) turns right to left.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ar from "@/locales/ar.json";
import fr from "@/locales/fr.json";

export const LANGUAGES = ["fr", "ar"] as const;
export type Lang = (typeof LANGUAGES)[number];
export const LANG_KEY = "agria-lang";

export function isLang(v: unknown): v is Lang {
  return v === "fr" || v === "ar";
}

export function savedLang(): Lang {
  try {
    const v = localStorage.getItem(LANG_KEY);
    return isLang(v) ? v : "fr";
  } catch {
    return "fr"; // private mode: French
  }
}

export function applyLang(lang: Lang) {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
}

export async function setLang(lang: Lang) {
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    /* private mode: not kept */
  }
  applyLang(lang);
  await i18n.changeLanguage(lang);
}

const initial = savedLang();
applyLang(initial);
void i18n.use(initReactI18next).init({
  resources: { fr: { translation: fr }, ar: { translation: ar } },
  lng: initial,
  fallbackLng: "fr",
  interpolation: { escapeValue: false }, // React escapes
  returnNull: false,
});

export default i18n;

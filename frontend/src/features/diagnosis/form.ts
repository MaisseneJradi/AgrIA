import { dataUrlToBlob } from "@/lib/image";
import type { Lang } from "@/lib/i18n";
import { CONTEXT_FIELDS, useDiagnosis } from "./store";

/** The form /diagnose expects, from what the farmer entered (src/api/main.py). Nothing is computed: empty fields are
 * left out, the month is today's month, the language is the one of the page. */
export function diagnoseForm(lang: Lang, now = new Date()): FormData {
  const s = useDiagnosis.getState();
  const form = new FormData();
  if (s.photo) form.append("photo", dataUrlToBlob(s.photo.dataUrl), "photo.jpg");
  form.append("message", s.message.trim());
  form.append("langue", lang);
  form.append("mois", String(now.getMonth() + 1));
  if (s.gouvernorat) form.append("gouvernorat", s.gouvernorat);
  if (s.crop) form.append("culture", s.crop);
  for (const k of CONTEXT_FIELDS) {
    const v = s.context[k];
    if (v !== undefined && v !== "") form.append(k, String(v));
  }
  return form;
}

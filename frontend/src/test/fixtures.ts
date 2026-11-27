// Answers of the API for the tests, typed with the generated types (a change of the backend schema breaks them).
// Copied from real answers of /identify and /diagnose (27/11/2026), shortened.
import type { DiagnoseAnswer, IdentifyAnswer } from "@/api/client";

export const TINY_JPEG =
  "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP////////////////////////////////////////////////////////////////////////////////////8AAgEB";

export const identifySure: IdentifyAnswer = {
  feuille: true,
  photo_plante: true,
  routage: "leaf",
  culture: "tomato",
  fr: "Tomate",
  ar: "طماطم",
  confiance: 0.96,
  sure: true,
  autre_plante: false,
  avis: { crop: "tomato", leaf: "tomato", diseases: "tomato", vlm: "tomato" },
  accord: 4,
  n_avis: 4,
  vlm: null,
  source_culture: "vote",
  desaccord_vlm: false,
  top3: [
    { code: "tomato", fr: "Tomate", confiance: 0.96 },
    { code: "olive", fr: "Olivier", confiance: 0.01 },
    { code: "autre_plante", fr: "Autre plante", confiance: 0.0 },
  ],
};

export const identifyUnsure: IdentifyAnswer = {
  ...identifySure,
  culture: "olive",
  confiance: 0.42,
  sure: false,
  top3: [
    { code: "olive", fr: "Olivier", confiance: 0.42 },
    { code: "tomato", fr: "Tomate", confiance: 0.22 },
  ],
};

export const identifyNotPlant: IdentifyAnswer = { feuille: false, photo_plante: false, routage: "other" };

const trace = [{ agent: "Coordinateur", action: "réponse envoyée (conseil)", duree_ms: 0 }];
const verification = { valide: true, raisons: [], avertissements: [], produits_verifies: [] };

export const diagnoseConseil: DiagnoseAnswer = {
  issue: "conseil",
  texte:
    "Diagnostic : Alternariose (brûlure alternarienne) (confiance 98 %).\n\n" +
    "Produits homologués en Tunisie pour ce cas (liste DGSVCIA du 22/05/2024) :\n" +
    "- Score 250 EC (Difenoconazole) : dose 0.5 l/ha ; délai avant récolte : 3 jours\n" +
    "  En boutique pour Score 250 EC : Score 250 EC (Difenoconazole 250 g/l, EC) — en stock — " +
    "https://www.agrishop.tn/store/category/Pesticides/Fongicides/score-250-ec/\n\n" +
    "Respectez la dose et le délai avant récolte indiqués sur l'étiquette. En cas de doute, contactez le CRDA.",
  langue: "fr",
  diagnostic: {
    routing: "leaf",
    task: "diseases",
    classe: "tomato__early_blight",
    nom: "Alternariose (brûlure alternarienne)",
    confiance: 98,
    fiable: true,
    raisons_doute: [],
    top3: [["tomato__early_blight", 0.98]],
    autre_modele: null,
    choix_du_modele: "combinaison",
  },
  culture: { code: "tomato", source: "agriculteur", predite: "tomato", confiance: 0.96 },
  produits: [{ nom: "Score 250 EC", dose: "0.5 l/ha", dar_jours: 3 }],
  engrais: [],
  avertissements: [],
  questions: [],
  sources: [],
  verification,
  contexte: {},
  questions_contexte: ["days_to_harvest", "market"],
  trace,
  duree_s: 0.4,
};

/** Not reliable: the agents ask questions. `produits` is filled on purpose (an API must never do it): the app must
 * still not show any product (rule 3 of the React plan). */
export const diagnoseUnreliable: DiagnoseAnswer = {
  ...diagnoseConseil,
  issue: "question",
  texte:
    "Je ne suis pas encore sûr du diagnostic.\n\nPour vous aider sans prendre de risque, dites-moi :\n" +
    "- Quelle est la culture ?\n- Pouvez-vous envoyer une photo plus proche d'une feuille atteinte ?",
  diagnostic: { ...diagnoseConseil.diagnostic, fiable: false, confiance: 38 },
  produits: [{ nom: "Score 250 EC", dose: "0.5 l/ha", dar_jours: 3 }],
  questions: ["Quelle est la culture ?"],
  questions_contexte: [],
};

export const diagnoseArabic: DiagnoseAnswer = {
  ...diagnoseConseil,
  langue: "ar",
  texte: "التشخيص: اللفحة المبكرة.\nاتصل بالـCRDA في حالة الشك.",
  questions_contexte: [],
};

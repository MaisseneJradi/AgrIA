// Answers of the API for the unit tests: REAL answers of /identify and /diagnose (tests/e2e/fixtures/api.json,
// written by the backend on 27/11/2026 with real photos: tomato with early blight, olive leaf not recognised), shared
// with the Playwright tests. tests/api/test_api.py validates the same shapes against src/api/schemas.py.
import type { Culture, DiagnoseAnswer, Gouvernorat, IdentifyAnswer } from "@/api/client";
import api from "../../tests/e2e/fixtures/api.json";

export const real = api as unknown as {
  identify_tomate: IdentifyAnswer;
  identify_olivier: IdentifyAnswer;
  conseil_fr: DiagnoseAnswer;
  conseil_ar: DiagnoseAnswer;
  question_fr: DiagnoseAnswer;
  question_ar: DiagnoseAnswer;
  cultures: Culture[];
  gouvernorats: Gouvernorat[];
};

export const TINY_JPEG =
  "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP////////////////////////////////////////////////////////////////////////////////////8AAgEB";

export const identifySure = real.identify_tomate;
export const identifyUnsure: IdentifyAnswer = {
  ...real.identify_tomate,
  culture: "olive",
  confiance: 0.42,
  sure: false,
  top3: [
    { code: "olive", fr: "Olivier", confiance: 0.42 },
    { code: "tomato", fr: "Tomate", confiance: 0.22 },
  ],
};
export const identifyNotPlant: IdentifyAnswer = { feuille: false, photo_plante: false, routage: "other" };

export const diagnoseConseil = real.conseil_fr;
export const diagnoseArabic = real.conseil_ar;

const treatments = real.conseil_fr.cartes.find((c) => c.type === "traitements");
/** Not reliable (real answer: questions). A product and a treatment card are ADDED on purpose (an API must never do
 * it): the app must still not show any product, dose or treatment card (rule 3 of the React plan). */
export const diagnoseUnreliable: DiagnoseAnswer = {
  ...real.question_fr,
  produits: [{ nom: "Score 250 EC", dose: "0.5 l/ha", dar_jours: 3 }],
  cartes: [...real.question_fr.cartes, ...(treatments ? [treatments] : [])],
};

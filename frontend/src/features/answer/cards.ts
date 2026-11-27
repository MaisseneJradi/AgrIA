import type { AnswerCard, DiagnoseAnswer } from "@/api/client";

type CardType = AnswerCard["type"];

/** Order of the cards on the screen (the API gives them in the order of the text): diagnosis first, then the
 * treatments, the fertilisers and water, prevention and advice, the notes. Every card of the API is shown: only the
 * order changes, never a word. */
const ORDER: CardType[] = [
  "autre_photo",
  "doute",
  "pistes",
  "sain",
  "hypothese",
  "diagnostic",
  "questions",
  "texte",
  "crda",
  "traitements",
  "securite",
  "rotation",
  "ecartes",
  "aucun_produit",
  "affiner",
  "engrais",
  "eau",
  "prevention",
  "conseils",
  "sources",
  "a_savoir",
  "fin",
];

/** When the diagnosis is not reliable only these cards may be shown: the doubt, the questions, the CRDA. Never a
 * product, a dose or a fertiliser, even partially, even if the API sent one (rule 3 of the React plan). */
const WHEN_UNRELIABLE = new Set<CardType>(["autre_photo", "doute", "pistes", "questions", "crda"]);

export function isReliable(answer: DiagnoseAnswer): boolean {
  return answer.issue === "conseil" && answer.diagnostic?.fiable !== false;
}

export function visibleCards(answer: DiagnoseAnswer): AnswerCard[] {
  const reliable = isReliable(answer);
  return [...answer.cartes]
    .filter((c) => reliable || WHEN_UNRELIABLE.has(c.type))
    .sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type));
}

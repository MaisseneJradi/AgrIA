// The last answers, on this device only (IndexedDB), as text: no photo is ever stored. At most MAX entries; the
// farmer can delete them all. An entry is always shown with its date, never as a new answer.
import { createStore, del, get, set } from "idb-keyval";
import type { AnswerCard, DiagnoseAnswer } from "@/api/client";

export const MAX = 10;
const store = () => createStore("agria", "kv");
const KEY = "history";

export interface HistoryEntry {
  id: string;
  date: string; // ISO date of the answer
  crop: string | null;
  issue: DiagnoseAnswer["issue"];
  niveau: NonNullable<DiagnoseAnswer["diagnostic"]>["niveau"] | null;
  langue: DiagnoseAnswer["langue"];
  texte: string;
  cartes: AnswerCard[];
}

export async function listHistory(): Promise<HistoryEntry[]> {
  try {
    return (await get<HistoryEntry[]>(KEY, store())) ?? [];
  } catch {
    return []; // private mode or no IndexedDB: no history
  }
}

export async function saveAnswer(
  answer: DiagnoseAnswer,
  crop: string | null,
  now = new Date(),
): Promise<void> {
  const entry: HistoryEntry = {
    id: `${now.getTime()}`,
    date: now.toISOString(),
    crop,
    issue: answer.issue,
    niveau: answer.diagnostic?.niveau ?? null,
    langue: answer.langue,
    texte: answer.texte,
    cartes: answer.cartes,
  };
  try {
    const all = await listHistory();
    await set(KEY, [entry, ...all].slice(0, MAX), store());
  } catch {
    /* not kept */
  }
}

export async function clearHistory(): Promise<void> {
  try {
    await del(KEY, store());
  } catch {
    /* nothing to delete */
  }
}

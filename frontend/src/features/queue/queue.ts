// One photo waiting for the network, with the farmer's consent: kept on the device (IndexedDB) with what he entered,
// sent when the network comes back. Only one at a time; the farmer can cancel it.
import { createStore, del, get, set } from "idb-keyval";
import type { PreparedPhoto } from "@/lib/image";
import type { Lang } from "@/lib/i18n";
import type { PlotContext } from "../diagnosis/store";

const store = () => createStore("agria", "kv");
const KEY = "pending";

export interface Pending {
  date: string; // when it was put aside
  photo: PreparedPhoto;
  crop: string;
  message: string;
  gouvernorat: string | null;
  context: PlotContext;
  langue: Lang;
}

export async function getPending(): Promise<Pending | null> {
  try {
    return (await get<Pending>(KEY, store())) ?? null;
  } catch {
    return null;
  }
}

export async function setPending(p: Pending): Promise<boolean> {
  try {
    await set(KEY, p, store());
    return true;
  } catch {
    return false;
  }
}

export async function clearPending(): Promise<void> {
  try {
    await del(KEY, store());
  } catch {
    /* nothing */
  }
}

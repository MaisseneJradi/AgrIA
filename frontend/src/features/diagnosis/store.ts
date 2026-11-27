// What the farmer entered, kept in the tab (sessionStorage): a reload or a retry never loses the photo, the crop or the
// context. The answer itself is NOT kept: after a reload it is asked again, so an old answer is never shown as new.
// The governorate is also kept on the device (localStorage) for the next diagnoses.
import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { DiagnoseAnswer, IdentifyAnswer } from "@/api/client";
import type { PreparedPhoto } from "@/lib/image";

export interface PlotContext {
  days_to_harvest?: number;
  market?: "local" | "export";
  organic?: "oui" | "non";
  greenhouse?: "oui" | "non";
  stage?: "early" | "spread";
  last_treatment_group?: string;
  area?: number;
}
export type ContextField = keyof PlotContext;
export const CONTEXT_FIELDS: ContextField[] = [
  "days_to_harvest",
  "market",
  "organic",
  "greenhouse",
  "stage",
  "last_treatment_group",
  "area",
];

export const GOV_KEY = "agria-gouvernorat";

function savedGov(): string | null {
  try {
    return localStorage.getItem(GOV_KEY);
  } catch {
    return null;
  }
}

interface DiagnosisState {
  photo: PreparedPhoto | null;
  identify: IdentifyAnswer | null;
  crop: string | null;
  message: string;
  gouvernorat: string | null;
  context: PlotContext;
  /** increased each time the farmer asks for an analysis: the answer screen sends one request per submission */
  submission: number;
  answer: DiagnoseAnswer | null;
  /** date the photo of this analysis was put aside without network (queue), null otherwise */
  queuedFrom: string | null;
  setPhoto: (photo: PreparedPhoto) => void;
  setIdentify: (r: IdentifyAnswer | null) => void;
  setCrop: (code: string) => void;
  setMessage: (text: string) => void;
  setGouvernorat: (gov: string | null) => void;
  setContext: (patch: Partial<PlotContext>) => void;
  submit: () => void;
  setAnswer: (a: DiagnoseAnswer | null) => void;
  reset: () => void;
}

const empty = {
  photo: null,
  identify: null,
  crop: null,
  message: "",
  context: {},
  answer: null,
  queuedFrom: null,
};

// sessionStorage can be full or blocked (private mode): the app keeps working, only without surviving a reload
const safeSession: StateStorage = {
  getItem: (k) => {
    try {
      return sessionStorage.getItem(k);
    } catch {
      return null;
    }
  },
  setItem: (k, v) => {
    try {
      sessionStorage.setItem(k, v);
    } catch {
      /* full: not kept */
    }
  },
  removeItem: (k) => {
    try {
      sessionStorage.removeItem(k);
    } catch {
      /* ignore */
    }
  },
};

export const useDiagnosis = create<DiagnosisState>()(
  persist(
    (set) => ({
      ...empty,
      gouvernorat: savedGov(),
      submission: 0,
      // a new photo: everything that depended on the old one is forgotten
      setPhoto: (photo) => set({ photo, identify: null, crop: null, answer: null, queuedFrom: null }),
      setIdentify: (identify) => set({ identify }),
      setCrop: (crop) => set({ crop, answer: null }),
      setMessage: (message) => set({ message }),
      setGouvernorat: (gouvernorat) => {
        try {
          if (gouvernorat) localStorage.setItem(GOV_KEY, gouvernorat);
          else localStorage.removeItem(GOV_KEY);
        } catch {
          /* not kept */
        }
        set({ gouvernorat });
      },
      // an emptied field is removed (it is then not sent: the agents ask for it if it matters)
      setContext: (patch) =>
        set((s) => ({
          context: Object.fromEntries(
            Object.entries({ ...s.context, ...patch }).filter(([, v]) => v !== undefined && v !== ""),
          ) as PlotContext,
        })),
      submit: () => set((s) => ({ submission: s.submission + 1, answer: null })),
      setAnswer: (answer) => set({ answer }),
      reset: () => set((s) => ({ ...empty, gouvernorat: s.gouvernorat })),
    }),
    {
      name: "agria-diagnostic",
      storage: createJSONStorage(() => safeSession),
      partialize: ({ photo, identify, crop, message, context, submission, queuedFrom }) => ({
        queuedFrom,
        photo,
        identify,
        crop,
        message,
        context,
        submission,
      }),
    },
  ),
);

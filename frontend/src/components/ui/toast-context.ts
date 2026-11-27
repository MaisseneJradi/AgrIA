import { createContext, useContext } from "react";

export type ToastTone = "info" | "success";
export interface ToastApi {
  show: (text: string, tone?: ToastTone) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);
export const TOAST_MS = 4000;

/** show("Copié", "success"): a short message at the bottom of the screen (ToastProvider). */
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}

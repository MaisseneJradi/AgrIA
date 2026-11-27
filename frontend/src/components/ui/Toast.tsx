import { CheckCircle2, Info, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ToastContext, TOAST_MS, type ToastTone } from "./toast-context";

interface ToastItem {
  id: number;
  text: string;
  tone: ToastTone;
}

/** Short messages at the bottom of the screen ("copied", "saved"), read by screen readers (aria-live polite), closed
 * after 4 s or by their button. At most 3 at a time. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const show = useCallback(
    (text: string, tone: ToastTone = "info") => {
      const id = next.current++;
      setItems((xs) => [...xs.slice(-2), { id, text, tone }]);
      setTimeout(() => dismiss(id), TOAST_MS);
    },
    [dismiss],
  );
  const api = useMemo(() => ({ show }), [show]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4"
      >
        {items.map((x) => {
          const Icon = x.tone === "success" ? CheckCircle2 : Info;
          return (
            <div
              key={x.id}
              className="pointer-events-auto flex w-full max-w-md animate-toast-in items-center gap-3 rounded-xl bg-text px-4 py-2 text-bg shadow-card"
            >
              <Icon className="size-5 shrink-0" aria-hidden="true" />
              <span className="flex-1">{x.text}</span>
              <button
                type="button"
                onClick={() => dismiss(x.id)}
                aria-label={t("common.dismiss")}
                className="-me-2 grid min-h-touch min-w-touch place-items-center rounded-full"
              >
                <X className="size-5" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

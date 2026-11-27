import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";

export interface Step {
  id: string;
  label: string;
}

export interface StepperProps {
  steps: Step[];
  /** index of the current step (0-based) */
  current: number;
  className?: string;
}

/** Where the farmer is in the flow: numbered circles joined by a line, the current one marked aria-current. In Arabic
 * the order runs right to left by itself (flex follows dir, the line uses the logical "end" side). */
export function Stepper({ steps, current, className }: StepperProps) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("stepper.label")} className={className}>
      <p className="mb-2 text-sm font-medium text-muted">
        {t("stepper.step", { current: current + 1, total: steps.length })}
      </p>
      <ol className="flex items-start">
        {steps.map((s, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li
              key={s.id}
              aria-current={active ? "step" : undefined}
              className="relative flex flex-1 flex-col items-center gap-1 text-center"
            >
              {i > 0 && (
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute end-1/2 top-5 h-1 w-full -translate-y-1/2 rounded",
                    i <= current ? "bg-primary" : "bg-border",
                  )}
                />
              )}
              <span
                className={cn(
                  "relative z-10 grid size-10 place-items-center rounded-full border-2 font-bold",
                  done && "border-primary bg-primary text-on-primary",
                  active && "border-primary bg-accent text-on-accent",
                  !done && !active && "border-border bg-surface text-muted",
                )}
              >
                {done ? <Check className="size-5" aria-hidden="true" /> : i + 1}
              </span>
              <span className={cn("text-sm", active ? "font-semibold text-text" : "text-muted")}>
                {s.label}
                {(done || active) && (
                  <span className="sr-only"> ({done ? t("stepper.done") : t("stepper.current")})</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

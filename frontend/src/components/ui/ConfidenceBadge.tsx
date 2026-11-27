import { CircleAlert, CircleCheck, CircleHelp, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";

/** The confidence in words. The level comes from the API (proposed field diagnostic.niveau, computed by the Diagnostic
 * agent with its own thresholds): the app never turns a probability into a level and never shows the probability. */
export type ConfidenceLevel = "sur" | "probable" | "incertain";

const STYLE: Record<ConfidenceLevel, { cls: string; icon: LucideIcon }> = {
  sur: { cls: "border-success bg-success-bg text-success", icon: CircleCheck },
  probable: { cls: "border-warning-strong bg-warning-bg text-warning", icon: CircleAlert },
  incertain: { cls: "border-danger-strong bg-danger-bg text-danger", icon: CircleHelp },
};

export function ConfidenceBadge({ level, className }: { level: ConfidenceLevel; className?: string }) {
  const { t } = useTranslation();
  const { cls, icon: Icon } = STYLE[level];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border-2 px-3 py-1 font-semibold",
        cls,
        className,
      )}
    >
      <Icon className="size-5" aria-hidden="true" />
      <span className="sr-only">{t("confidence.label")}: </span>
      {t(`confidence.${level}`)}
    </span>
  );
}

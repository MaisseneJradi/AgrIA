import type { LucideIcon } from "lucide-react";
import { AlertTriangle, CheckCircle2, Info, WifiOff, X } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";

export type AlertTone = "info" | "success" | "warning" | "danger";

export interface AlertProps {
  tone?: AlertTone;
  title?: ReactNode;
  icon?: LucideIcon;
  /** a button (retry...) under the text */
  action?: ReactNode;
  onDismiss?: () => void;
  className?: string;
  children?: ReactNode;
}

const STYLE: Record<AlertTone, { box: string; icon: LucideIcon }> = {
  info: { box: "bg-info-bg text-info border-border", icon: Info },
  success: { box: "bg-success-bg text-success border-success", icon: CheckCircle2 },
  warning: { box: "bg-warning-bg text-warning border-warning-strong", icon: AlertTriangle },
  danger: { box: "bg-danger-bg text-danger border-danger-strong", icon: WifiOff },
};

/** A message. Warnings and errors are announced at once (role alert), the others politely (role status). */
export function Alert({ tone = "info", title, icon, action, onDismiss, className, children }: AlertProps) {
  const { t } = useTranslation();
  const Icon = icon ?? STYLE[tone].icon;
  return (
    <div
      role={tone === "danger" || tone === "warning" ? "alert" : "status"}
      className={cn("flex gap-3 rounded-xl border-2 p-4", STYLE[tone].box, className)}
    >
      <Icon className="mt-0.5 size-6 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div>{children}</div>}
        {action && <div className="pt-2">{action}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={t("common.dismiss")}
          className="-me-2 -mt-2 grid min-h-touch min-w-touch place-items-center rounded-full hover:bg-black/5"
        >
          <X className="size-5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

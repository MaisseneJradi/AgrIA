import type { LucideIcon } from "lucide-react";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type CardTone = "default" | "warning" | "danger" | "success";

export interface CardProps {
  title?: ReactNode;
  icon?: LucideIcon;
  /** heading level of the title (the page keeps one h1) */
  level?: 2 | 3;
  tone?: CardTone;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}

const TONES: Record<CardTone, string> = {
  default: "border-border",
  warning: "border-warning-strong",
  danger: "border-danger-strong",
  success: "border-success",
};

/** A section of the answer: an icon, a title, the content. The coloured edge is on the start side. */
export function Card({
  title,
  icon: Icon,
  level = 2,
  tone = "default",
  actions,
  className,
  children,
}: CardProps) {
  const id = useId();
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section
      aria-labelledby={title ? id : undefined}
      className={cn(
        "rounded-card border border-s-4 bg-surface p-4 shadow-card sm:p-5",
        TONES[tone],
        className,
      )}
    >
      {title && (
        <div className="mb-3 flex items-center gap-3">
          {Icon && (
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-surface-2 text-text">
              <Icon className="size-5" aria-hidden="true" />
            </span>
          )}
          <Heading id={id} className="flex-1 text-xl font-semibold leading-tight">
            {title}
          </Heading>
          {actions}
        </div>
      )}
      <div className="space-y-3">{children}</div>
    </section>
  );
}

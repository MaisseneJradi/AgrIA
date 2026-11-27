import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";

/** A grey block standing for content that is loading (hidden from screen readers). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-lg bg-surface-2", className)} />;
}

/** Several lines of skeleton, announced once as "loading" (role status). */
export function SkeletonBlock({
  lines = 3,
  label,
  className,
}: {
  lines?: number;
  label?: string;
  className?: string;
}) {
  const { t } = useTranslation();
  return (
    <div role="status" aria-live="polite" className={cn("space-y-3", className)}>
      <span className="sr-only">{label ?? t("common.loading")}</span>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

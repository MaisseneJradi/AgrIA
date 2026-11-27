import type { LucideIcon } from "lucide-react";
import { Check } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export interface ChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> {
  selected: boolean;
  onSelectedChange?: (selected: boolean) => void;
  icon?: LucideIcon;
}

/** A tappable choice (crop, market, yes / no): a toggle button, aria-pressed tells its state. */
export function Chip({
  selected,
  onSelectedChange,
  icon: Icon,
  className,
  children,
  onClick,
  ...rest
}: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={(e) => {
        onClick?.(e);
        onSelectedChange?.(!selected);
      }}
      className={cn(
        "inline-flex min-h-touch items-center gap-2 rounded-full border-2 px-4 py-2 text-base font-medium transition-colors",
        selected
          ? "border-primary bg-primary text-on-primary"
          : "border-border bg-surface text-text hover:bg-surface-2",
        className,
      )}
      {...rest}
    >
      {selected ? (
        <Check className="size-5 shrink-0" aria-hidden="true" />
      ) : (
        Icon && <Icon className="size-5 shrink-0" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}

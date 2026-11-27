import type { LucideIcon } from "lucide-react";
import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** icon before the label (start side: left in French, right in Arabic) */
  icon?: LucideIcon;
  /** icon after the label */
  iconEnd?: LucideIcon;
  /** mirror the icons in right-to-left (arrows, chevrons) */
  mirrorIcon?: boolean;
  /** shows a spinner, disables the button and sets aria-busy */
  loading?: boolean;
  /** full width */
  block?: boolean;
}

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-primary text-on-primary hover:bg-primary/90 border-transparent",
  secondary: "bg-surface text-text border-border hover:bg-surface-2",
  ghost: "bg-transparent text-text border-transparent hover:bg-surface-2",
  danger: "bg-danger-bg text-danger border-danger-strong hover:bg-danger-bg/80",
};

/** Touch target of at least 48 px, visible focus, icon and label in both writing directions. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    icon: Icon,
    iconEnd: IconEnd,
    mirrorIcon,
    loading,
    block,
    className,
    children,
    disabled,
    type,
    ...rest
  },
  ref,
) {
  const iconClass = cn("size-5 shrink-0", mirrorIcon && "rtl:-scale-x-100");
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex min-h-touch min-w-touch items-center justify-center gap-2 rounded-xl border-2 px-5 py-2",
        "text-base font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 className="size-5 shrink-0 animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon className={iconClass} aria-hidden="true" />
      )}
      {children}
      {IconEnd && !loading && <IconEnd className={iconClass} aria-hidden="true" />}
    </button>
  );
});

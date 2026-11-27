import { Moon, Smartphone, Sun, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";
import { savedTheme, setTheme, type Theme } from "@/lib/theme";

const OPTIONS: Array<{ value: Theme; icon: LucideIcon }> = [
  { value: "light", icon: Sun },
  { value: "dark", icon: Moon },
  { value: "system", icon: Smartphone },
];

/** Light, dark, or like the phone. */
export function ThemeSwitch({ className }: { className?: string }) {
  const { t } = useTranslation();
  const [theme, setState] = useState<Theme>(savedTheme);
  return (
    <div
      role="group"
      aria-label={t("theme.label")}
      className={cn("inline-flex rounded-full bg-surface-2 p-1", className)}
    >
      {OPTIONS.map(({ value, icon: Icon }) => (
        <button
          key={value}
          type="button"
          aria-pressed={theme === value}
          aria-label={t(`theme.${value}`)}
          title={t(`theme.${value}`)}
          onClick={() => {
            setTheme(value);
            setState(value);
          }}
          className={cn(
            "grid min-h-touch min-w-touch place-items-center rounded-full",
            theme === value ? "bg-primary text-on-primary" : "text-text",
          )}
        >
          <Icon className="size-5" aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}

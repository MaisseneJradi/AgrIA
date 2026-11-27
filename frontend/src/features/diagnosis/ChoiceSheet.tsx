import { Check, Search, type LucideIcon } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { BottomSheet } from "@/components/ui";
import { cn } from "@/lib/cn";
import { fold } from "@/lib/text";

export interface Choice {
  value: string;
  label: string;
  /** other spelling searched too (the French name when the page is in Arabic, and the reverse) */
  alt?: string;
  icon?: LucideIcon;
}

/** A list to pick one item from (crops, governorates), in a panel from the bottom, with a search field. */
export function ChoiceSheet({
  open,
  onOpenChange,
  title,
  searchLabel,
  choices,
  selected,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  searchLabel: string;
  choices: Choice[];
  selected: string | null;
  onSelect: (value: string) => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const id = useId();
  const shown = useMemo(() => {
    const q = fold(query);
    return q ? choices.filter((c) => fold(`${c.label} ${c.alt ?? ""}`).includes(q)) : choices;
  }, [choices, query]);
  return (
    <BottomSheet
      open={open}
      onOpenChange={(o) => {
        if (!o) setQuery("");
        onOpenChange(o);
      }}
      title={title}
    >
      <label htmlFor={id} className="sr-only">
        {searchLabel}
      </label>
      <div className="relative mb-3">
        <Search
          className="pointer-events-none absolute start-3 top-1/2 size-5 -translate-y-1/2 text-muted"
          aria-hidden="true"
        />
        <input
          id={id}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={searchLabel}
          className="min-h-touch w-full rounded-xl border-2 border-border bg-bg py-2 pe-3 ps-11 text-base"
        />
      </div>
      {shown.length === 0 ? (
        <p className="py-4 text-center text-muted">{t("crop.noResult")}</p>
      ) : (
        <ul className="space-y-1">
          {shown.map((c) => {
            const Icon = c.icon;
            const isSel = c.value === selected;
            return (
              <li key={c.value}>
                <button
                  type="button"
                  aria-pressed={isSel}
                  onClick={() => {
                    onSelect(c.value);
                    setQuery("");
                    onOpenChange(false);
                  }}
                  className={cn(
                    "flex min-h-touch w-full items-center gap-3 rounded-xl px-3 py-2 text-start text-base",
                    isSel ? "bg-primary text-on-primary" : "hover:bg-surface-2",
                  )}
                >
                  {Icon && <Icon className="size-5 shrink-0" aria-hidden="true" />}
                  <span className="flex-1">{c.label}</span>
                  {isSel && <Check className="size-5" aria-hidden="true" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </BottomSheet>
  );
}

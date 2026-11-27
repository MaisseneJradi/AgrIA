import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Chip } from "@/components/ui";
import type { ContextField, PlotContext } from "./store";

const DAYS = [3, 7, 14, 30];

/** The context of the plot as taps (chips) or a short entry. The farmer's own answers: nothing is guessed or
 * computed here; an empty field is simply not sent, and the agents ask for it when it would change the answer. */
export function ContextFields({
  fields,
  value,
  onChange,
}: {
  fields: ContextField[];
  value: PlotContext;
  onChange: (patch: Partial<PlotContext>) => void;
}) {
  const { t } = useTranslation();
  const base = useId();
  const toggle = <K extends ContextField>(k: K, v: PlotContext[K]) =>
    onChange({ [k]: value[k] === v ? undefined : v } as Partial<PlotContext>);

  return (
    <div className="space-y-5">
      {fields.includes("days_to_harvest") && (
        <fieldset className="space-y-2">
          <legend className="font-semibold">{t("context.days")}</legend>
          <div className="flex flex-wrap gap-2">
            {DAYS.map((n) => (
              <Chip
                key={n}
                selected={value.days_to_harvest === n}
                onSelectedChange={() => toggle("days_to_harvest", n)}
              >
                {t("context.daysValue", { n })}
              </Chip>
            ))}
          </div>
          <label htmlFor={`${base}-days`} className="block text-sm text-muted">
            {t("context.daysOther")}
          </label>
          <input
            id={`${base}-days`}
            type="number"
            inputMode="numeric"
            min={0}
            max={365}
            value={value.days_to_harvest ?? ""}
            onChange={(e) =>
              onChange({ days_to_harvest: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            className="min-h-touch w-32 rounded-xl border-2 border-border bg-surface px-3 text-base"
          />
        </fieldset>
      )}

      {fields.includes("market") && (
        <fieldset className="space-y-2">
          <legend className="font-semibold">{t("context.market")}</legend>
          <div className="flex flex-wrap gap-2">
            {(["local", "export"] as const).map((m) => (
              <Chip key={m} selected={value.market === m} onSelectedChange={() => toggle("market", m)}>
                {t(`context.${m}`)}
              </Chip>
            ))}
          </div>
        </fieldset>
      )}

      {(["organic", "greenhouse"] as const)
        .filter((k) => fields.includes(k))
        .map((k) => (
          <fieldset key={k} className="space-y-2">
            <legend className="font-semibold">{t(`context.${k}`)}</legend>
            <div className="flex flex-wrap gap-2">
              {(["oui", "non"] as const).map((v) => (
                <Chip key={v} selected={value[k] === v} onSelectedChange={() => toggle(k, v)}>
                  {t(v === "oui" ? "context.yes" : "context.no")}
                </Chip>
              ))}
            </div>
          </fieldset>
        ))}

      {fields.includes("stage") && (
        <fieldset className="space-y-2">
          <legend className="font-semibold">{t("context.stage")}</legend>
          <div className="flex flex-wrap gap-2">
            {(["early", "spread"] as const).map((s) => (
              <Chip key={s} selected={value.stage === s} onSelectedChange={() => toggle("stage", s)}>
                {t(`context.${s}`)}
              </Chip>
            ))}
          </div>
        </fieldset>
      )}

      {fields.includes("last_treatment_group") && (
        <div className="space-y-2">
          <label htmlFor={`${base}-last`} className="block font-semibold">
            {t("context.last")}
          </label>
          <input
            id={`${base}-last`}
            type="text"
            maxLength={80}
            placeholder={t("context.lastPh")}
            value={value.last_treatment_group ?? ""}
            onChange={(e) => onChange({ last_treatment_group: e.target.value || undefined })}
            className="min-h-touch w-full rounded-xl border-2 border-border bg-surface px-3 text-base"
          />
        </div>
      )}

      {fields.includes("area") && (
        <div className="space-y-2">
          <label htmlFor={`${base}-area`} className="block font-semibold">
            {t("context.area")}
          </label>
          <input
            id={`${base}-area`}
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            value={value.area ?? ""}
            onChange={(e) => onChange({ area: e.target.value === "" ? undefined : Number(e.target.value) })}
            className="min-h-touch w-32 rounded-xl border-2 border-border bg-surface px-3 text-base"
          />
        </div>
      )}
    </div>
  );
}

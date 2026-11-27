import { ChevronDown, MapPin, Mic, MicOff, ScanSearch } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useGouvernorats } from "@/api/queries";
import { Button, Card } from "@/components/ui";
import type { Lang } from "@/lib/i18n";
import { listen, speechCtor } from "@/lib/speech";
import { ChoiceSheet } from "./ChoiceSheet";
import { ContextFields } from "./ContextFields";
import { StepPage } from "./StepPage";
import { STEP_PATH } from "./steps";
import { CONTEXT_FIELDS, useDiagnosis } from "./store";

/** Step 3: an optional message (typed or dictated), the governorate (remembered on the device) and the optional
 * context of the plot. Then the analysis is asked for. */
export function ContextStep() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const navigate = useNavigate();
  const { message, setMessage, gouvernorat, setGouvernorat, context, setContext, submit } = useDiagnosis();
  const govs = useGouvernorats();
  const [sheet, setSheet] = useState(false);
  const [listening, setListening] = useState(false);
  const stop = useRef<(() => void) | null>(null);
  const msgId = useId();
  const canDictate = speechCtor() !== null;
  useEffect(() => () => stop.current?.(), []);

  const govLabel = govs.data?.find((g) => g.fr === gouvernorat)?.[lang] ?? gouvernorat;

  function dictate() {
    if (listening) {
      stop.current?.();
      return;
    }
    setListening(true);
    stop.current = listen(
      lang,
      (text) =>
        setMessage(useDiagnosis.getState().message ? `${useDiagnosis.getState().message} ${text}` : text),
      () => {
        setListening(false);
        stop.current = null;
      },
    );
  }

  return (
    <StepPage
      step="context"
      title={t("context.title")}
      actions={
        <>
          <Button variant="secondary" onClick={() => navigate(STEP_PATH.crop)}>
            {t("nav.back")}
          </Button>
          <Button
            block
            icon={ScanSearch}
            onClick={() => {
              submit();
              navigate(STEP_PATH.answer);
            }}
          >
            {t("nav.analyse")}
          </Button>
        </>
      }
    >
      <p className="text-muted">{t("context.intro")}</p>

      <div className="space-y-2">
        <label htmlFor={msgId} className="block font-semibold">
          {t("context.message")}
        </label>
        <textarea
          id={msgId}
          rows={3}
          value={message}
          maxLength={500}
          placeholder={t("context.messagePh")}
          onChange={(e) => setMessage(e.target.value)}
          className="w-full rounded-xl border-2 border-border bg-surface p-3 text-base"
        />
        {canDictate && (
          <Button
            variant="secondary"
            icon={listening ? MicOff : Mic}
            onClick={dictate}
            aria-pressed={listening}
          >
            {listening ? t("context.stopDictate") : t("context.dictate")}
          </Button>
        )}
        {listening && (
          <p role="status" className="text-muted">
            {t("context.listening")}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <p className="font-semibold">{t("context.gov")}</p>
        <Button variant="secondary" icon={MapPin} iconEnd={ChevronDown} block onClick={() => setSheet(true)}>
          {govLabel ?? t("context.govChoose")}
        </Button>
      </div>

      <Card title={t("context.more")} level={2}>
        <ContextFields fields={CONTEXT_FIELDS} value={context} onChange={setContext} />
      </Card>

      <ChoiceSheet
        open={sheet}
        onOpenChange={setSheet}
        title={t("context.gov")}
        searchLabel={t("context.govSearch")}
        selected={gouvernorat}
        onSelect={setGouvernorat}
        choices={(govs.data ?? []).map((g) => ({
          value: g.fr,
          label: g[lang],
          alt: g[lang === "ar" ? "fr" : "ar"],
        }))}
      />
    </StepPage>
  );
}

import { useMutation } from "@tanstack/react-query";
import { Camera, List, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import { useCultures } from "@/api/queries";
import { Alert, Button, SkeletonBlock } from "@/components/ui";
import { cn } from "@/lib/cn";
import { dataUrlToBlob } from "@/lib/image";
import type { Lang } from "@/lib/i18n";
import { ChoiceSheet } from "./ChoiceSheet";
import { cropIcon, cropName } from "./crops";
import { describeError } from "./errors";
import { StepPage } from "./StepPage";
import { STEP_PATH } from "./steps";
import { useDiagnosis } from "./store";

/** Step 2: the crop. The 3 crops /identify sees on the photo as big buttons (the first one marked "proposed" only
 * when the API says it is sure), or any crop of /cultures. Nothing is chosen for the farmer: he taps to confirm. */
export function CropStep() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const navigate = useNavigate();
  const { photo, identify, crop, setIdentify, setCrop } = useDiagnosis();
  const cultures = useCultures();
  const [sheet, setSheet] = useState(false);
  const sentFor = useRef<string | null>(null);

  const run = useMutation({
    mutationFn: (dataUrl: string) => api.identify(dataUrlToBlob(dataUrl)),
    onSuccess: setIdentify,
  });
  const { mutate } = run;

  // one request per photo (also after a reload, and only once under React's StrictMode)
  useEffect(() => {
    if (photo && !identify && sentFor.current !== photo.dataUrl) {
      sentFor.current = photo.dataUrl;
      mutate(photo.dataUrl);
    }
  }, [photo, identify, mutate]);

  const known = new Set((cultures.data ?? []).map((c) => c.code));
  const top = (identify?.top3 ?? []).filter((x) => known.has(x.code)).map((x) => x.code);
  const suggested = identify?.sure && !identify.autre_plante ? identify.culture : null;
  const shown = crop && !top.includes(crop) ? [...top, crop] : top;
  const refused = identify?.photo_plante === false;
  const error = run.isError ? describeError(run.error, t) : null;

  return (
    <StepPage
      step="crop"
      title={t("crop.title")}
      actions={
        <>
          <Button variant="secondary" onClick={() => navigate(STEP_PATH.photo)}>
            {t("nav.back")}
          </Button>
          <Button block disabled={!crop} onClick={() => navigate(STEP_PATH.context)}>
            {t("nav.continue")}
          </Button>
        </>
      }
    >
      {photo && (
        <img
          src={photo.dataUrl}
          alt={t("photo.preview")}
          className="mx-auto max-h-40 w-auto rounded-xl border border-border object-contain"
        />
      )}

      {run.isPending && <SkeletonBlock lines={3} label={t("crop.identifying")} />}
      {run.isPending && <p className="text-muted">{t("crop.identifying")}</p>}

      {error && (
        <Alert
          tone="danger"
          title={t("error.title")}
          action={
            error.kind === "photo" ? (
              <Button variant="secondary" icon={Camera} onClick={() => navigate(STEP_PATH.photo)}>
                {t("crop.retake")}
              </Button>
            ) : (
              <Button variant="secondary" icon={RotateCcw} onClick={() => photo && mutate(photo.dataUrl)}>
                {t("common.retry")}
              </Button>
            )
          }
        >
          {error.text}
        </Alert>
      )}

      {refused && (
        <Alert
          tone="warning"
          title={t("crop.notPlantTitle")}
          action={
            <Button variant="secondary" icon={Camera} onClick={() => navigate(STEP_PATH.photo)}>
              {t("crop.retake")}
            </Button>
          }
        >
          {t("crop.notPlant")}
        </Alert>
      )}
      {identify && !refused && !identify.feuille && <Alert tone="info">{t("crop.notLeaf")}</Alert>}
      {identify?.autre_plante && identify.sure && <Alert tone="info">{t("crop.notCovered")}</Alert>}

      {shown.length > 0 && (
        <section aria-labelledby="crop-suggestions" className="space-y-3">
          <h2 id="crop-suggestions" className="text-lg font-semibold">
            {t("crop.suggestions")}
          </h2>
          <p className="text-muted">{t("crop.chooseHint")}</p>
          <div className="grid gap-3">
            {shown.map((code) => {
              const Icon = cropIcon(code);
              const selected = crop === code;
              return (
                <button
                  key={code}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setCrop(code)}
                  className={cn(
                    "flex min-h-16 items-center gap-4 rounded-card border-2 px-4 py-3 text-start text-lg font-semibold",
                    selected
                      ? "border-primary bg-primary text-on-primary"
                      : "border-border bg-surface text-text hover:bg-surface-2",
                  )}
                >
                  <Icon className="size-7 shrink-0" aria-hidden="true" />
                  <span className="flex-1">{cropName(code, cultures.data, lang)}</span>
                  {code === suggested && (
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-sm",
                        selected ? "bg-on-primary/20" : "bg-success-bg text-success",
                      )}
                    >
                      {t("crop.suggested")}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {(identify || error) && (
        <Button variant="secondary" icon={List} block onClick={() => setSheet(true)}>
          {t("crop.other")}
        </Button>
      )}
      {crop && (
        <p role="status" className="font-semibold">
          {t("crop.chosen", { name: cropName(crop, cultures.data, lang) })}
        </p>
      )}

      <ChoiceSheet
        open={sheet}
        onOpenChange={setSheet}
        title={t("crop.other")}
        searchLabel={t("crop.search")}
        selected={crop}
        onSelect={setCrop}
        choices={(cultures.data ?? []).map((c) => ({
          value: c.code,
          label: c[lang],
          alt: c[lang === "ar" ? "fr" : "ar"],
          icon: cropIcon(c.code),
        }))}
      />
    </StepPage>
  );
}

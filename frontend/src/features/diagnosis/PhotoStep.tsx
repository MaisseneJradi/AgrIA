import { Camera, Focus, ImagePlus, Leaf, MonitorX, Sun } from "lucide-react";
import { useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Card } from "@/components/ui";
import { preparePhoto } from "@/lib/image";
import { describeError } from "./errors";
import { StepPage } from "./StepPage";
import { STEP_PATH } from "./steps";
import { useDiagnosis } from "./store";

const TIPS = [
  { key: "tipLeaf", icon: Leaf },
  { key: "tipClose", icon: Focus },
  { key: "tipLight", icon: Sun },
  { key: "tipNoScreen", icon: MonitorX },
] as const;

/** Step 1: the camera (back camera) or the gallery; the photo is turned upright and reduced on the phone. */
export function PhotoStep() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const photo = useDiagnosis((s) => s.photo);
  const setPhoto = useDiagnosis((s) => s.setPhoto);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const camera = useRef<HTMLInputElement>(null);
  const gallery = useRef<HTMLInputElement>(null);
  const ids = { camera: useId(), gallery: useId() };

  async function onFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      setPhoto(await preparePhoto(file));
    } catch (e) {
      setError(describeError(e, t).text);
    } finally {
      setBusy(false);
    }
  }

  const inputs = (
    <>
      <input
        id={ids.camera}
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="camera-input"
        onChange={(e) => {
          void onFile(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <input
        id={ids.gallery}
        ref={gallery}
        type="file"
        accept="image/*"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="gallery-input"
        onChange={(e) => {
          void onFile(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
    </>
  );

  return (
    <StepPage
      step="photo"
      title={t("photo.title")}
      actions={
        photo ? (
          <Button block onClick={() => navigate(STEP_PATH.crop)}>
            {t("nav.continue")}
          </Button>
        ) : undefined
      }
    >
      {inputs}
      {photo ? (
        <figure className="space-y-3">
          <img
            src={photo.dataUrl}
            alt={t("photo.preview")}
            width={photo.width}
            height={photo.height}
            className="mx-auto max-h-[50vh] w-auto rounded-card border border-border object-contain"
          />
          <figcaption className="sr-only">{t("photo.preview")}</figcaption>
          <div className="flex flex-wrap justify-center gap-2">
            <Button variant="secondary" icon={Camera} onClick={() => camera.current?.click()} loading={busy}>
              {t("photo.change")}
            </Button>
          </div>
        </figure>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            icon={Camera}
            loading={busy}
            onClick={() => camera.current?.click()}
            className="min-h-24 text-lg"
          >
            {busy ? t("photo.preparing") : t("photo.take")}
          </Button>
          <Button
            variant="secondary"
            icon={ImagePlus}
            disabled={busy}
            onClick={() => gallery.current?.click()}
            className="min-h-24 text-lg"
          >
            {t("photo.gallery")}
          </Button>
        </div>
      )}
      {error && <Alert tone="warning">{error}</Alert>}
      <Card title={t("photo.tipsTitle")} level={2}>
        <ul className="space-y-3">
          {TIPS.map(({ key, icon: Icon }) => (
            <li key={key} className="flex items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-success-bg text-success">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <span>{t(`photo.${key}`)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </StepPage>
  );
}

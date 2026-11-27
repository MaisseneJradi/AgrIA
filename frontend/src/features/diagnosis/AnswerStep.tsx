import { useMutation } from "@tanstack/react-query";
import { Camera, Languages, MessageSquareText, Plus, RotateCcw, SlidersHorizontal } from "lucide-react";
import { Fragment, useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api, type DiagnoseAnswer } from "@/api/client";
import { useCultures } from "@/api/queries";
import { Alert, Button, Card, SkeletonBlock } from "@/components/ui";
import type { Lang } from "@/lib/i18n";
import { ContextFields } from "./ContextFields";
import { cropName } from "./crops";
import { describeError } from "./errors";
import { StepPage } from "./StepPage";
import { STEP_PATH } from "./steps";
import { diagnoseForm } from "./form";
import { CONTEXT_FIELDS, useDiagnosis, type ContextField } from "./store";

/** Step 4 (step 2 of the React plan): the answer as the agents wrote it and the Vérificateur checked it, shown as is.
 * The cards (treatments, safety, sources) come at step 3 of the plan. */
export function AnswerStep() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const navigate = useNavigate();
  const { crop, context, setContext, submission, submit, answer, setAnswer, reset } = useDiagnosis();
  const cultures = useCultures();
  const sent = useRef<number | null>(null);

  const run = useMutation({
    mutationFn: () => api.diagnose(diagnoseForm(lang)),
    onSuccess: setAnswer,
  });
  const { mutate } = run;

  // one request per submission ("Analyser", "Relancer", retry); after a reload the answer is asked again
  useEffect(() => {
    if (!answer && sent.current !== submission) {
      sent.current = submission;
      mutate();
    }
  }, [answer, submission, mutate]);

  const error = run.isError ? describeError(run.error, t) : null;
  const asked = (answer?.questions_contexte ?? []).filter((f): f is ContextField =>
    (CONTEXT_FIELDS as string[]).includes(f),
  );

  return (
    <StepPage
      step="answer"
      title={t("answer.title")}
      actions={
        <Button
          block
          icon={Plus}
          onClick={() => {
            reset();
            navigate(STEP_PATH.photo);
          }}
        >
          {t("nav.newDiagnosis")}
        </Button>
      }
    >
      {run.isPending && (
        <Card>
          <p className="font-semibold" aria-hidden="true">
            {t("answer.loading")}
          </p>
          <p className="text-muted">{t("answer.loadingHint")}</p>
          <SkeletonBlock lines={6} label={t("answer.loading")} />
        </Card>
      )}

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
              <Button variant="secondary" icon={RotateCcw} onClick={submit}>
                {t("common.retry")}
              </Button>
            )
          }
        >
          {error.text}
        </Alert>
      )}

      {answer && (
        <AnswerView
          answer={answer}
          cropLabel={cropName(crop, cultures.data, lang)}
          pageLang={lang}
          onOtherLang={submit}
          onRetake={() => navigate(STEP_PATH.photo)}
        />
      )}

      {answer && asked.length > 0 && (
        <Card title={t("answer.refineTitle")} icon={SlidersHorizontal} tone="warning">
          <p>{t("answer.refineIntro")}</p>
          <ContextFields fields={asked} value={context} onChange={setContext} />
          <Button icon={RotateCcw} block onClick={submit}>
            {t("answer.refine")}
          </Button>
        </Card>
      )}
    </StepPage>
  );
}

const URL_RE = /(https?:\/\/[^\s)]+)/g;

/** The text of the answer, line by line, links clickable (left to right inside Arabic text). Nothing is added,
 * removed or reordered: this is the text the Vérificateur checked. */
export function AnswerText({ text, lang }: { text: string; lang: "fr" | "ar" }) {
  return (
    <div
      lang={lang}
      dir={lang === "ar" ? "rtl" : "ltr"}
      className="whitespace-pre-wrap break-words leading-relaxed"
    >
      {text.split(URL_RE).map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            dir="ltr"
            className="break-all font-medium text-text underline underline-offset-2"
          >
            {part}
          </a>
        ) : lang === "ar" ? (
          <Fragment key={i}>{isolateLatin(part)}</Fragment>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </div>
  );
}

// a run of French or Latin text inside Arabic (product names, doses, "Alternariose (brûlure alternarienne)"): starts
// with a Latin letter or a digit, ends with one (or a closing bracket, a % or a unit dot)
const LATIN_RUN = /([A-Za-zÀ-ÖØ-öø-ÿŒœ0-9][A-Za-zÀ-ÖØ-öø-ÿŒœ0-9 .,;:/%()+'’-]*[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9)%.])/g;

/** In an Arabic answer, each Latin run is isolated left to right (<bdi dir="ltr">), so that its brackets and numbers
 * stay in place. Display only: the characters are the same (tested). */
function isolateLatin(text: string) {
  const out: ReactNode[] = [];
  text.split(LATIN_RUN).forEach((part, i) => {
    if (i % 2 === 0) {
      out.push(part);
      return;
    }
    // a closing bracket of the Arabic sentence around the run stays outside it
    let run = part;
    let tail = "";
    while (run.endsWith(")") && count(run, ")") > count(run, "(")) {
      tail = ")" + tail;
      run = run.slice(0, -1);
    }
    out.push(
      <bdi key={i} dir="ltr">
        {run}
      </bdi>,
      tail,
    );
  });
  return out;
}

function count(s: string, ch: string): number {
  return s.split(ch).length - 1;
}

export function AnswerView({
  answer,
  cropLabel,
  pageLang,
  onOtherLang,
  onRetake,
}: {
  answer: DiagnoseAnswer;
  cropLabel: string;
  pageLang: Lang;
  onOtherLang: () => void;
  onRetake: () => void;
}) {
  const { t } = useTranslation();
  const tone = answer.issue === "conseil" ? "success" : answer.issue === "crda" ? "danger" : "warning";
  return (
    <div aria-live="polite" className="space-y-4">
      {answer.langue !== pageLang && (
        <Alert
          tone="info"
          icon={Languages}
          action={
            <Button variant="secondary" icon={Languages} onClick={onOtherLang}>
              {t("answer.inLang")}
            </Button>
          }
        >
          {t("answer.otherLang")}
        </Alert>
      )}
      <Card
        title={t(`answer.issue.${answer.issue}`)}
        icon={MessageSquareText}
        tone={tone}
        actions={
          cropLabel ? (
            <span className="rounded-full bg-surface-2 px-3 py-1 text-sm font-semibold">{cropLabel}</span>
          ) : undefined
        }
      >
        <AnswerText text={answer.texte} lang={answer.langue} />
      </Card>
      {answer.issue === "autre_photo" && (
        <Button variant="secondary" icon={Camera} block onClick={onRetake}>
          {t("answer.retakePhoto")}
        </Button>
      )}
    </div>
  );
}

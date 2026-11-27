import { useMutation } from "@tanstack/react-query";
import { Camera, Clock, Languages, Plus, RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api, NetworkError, type DiagnoseAnswer } from "@/api/client";
import { useCultures } from "@/api/queries";
import { Alert, Button, Card, SkeletonBlock } from "@/components/ui";
import type { Lang } from "@/lib/i18n";
import { formatDate } from "@/lib/format";
import { useOnline } from "@/lib/useOnline";
import { AnswerCardView } from "../answer/AnswerCards";
import { isReliable, visibleCards } from "../answer/cards";
import { AnswerActions, TraceView } from "../answer/AnswerExtras";
import { saveAnswer } from "../history/history";
import { clearPending, getPending, setPending, type Pending } from "../queue/queue";
import { FeedbackCard } from "../test-mode/FeedbackCard";
import { ContextFields } from "./ContextFields";
import { cropName } from "./crops";
import { describeError } from "./errors";
import { diagnoseForm } from "./form";
import { StepPage } from "./StepPage";
import { STEP_PATH } from "./steps";
import { CONTEXT_FIELDS, useDiagnosis, type ContextField } from "./store";

/** Step 4: the answer of the agents as cards (the same text the Vérificateur checked, cut where the API cut it),
 * the questions to refine, how AgrIA decided, share / print / read aloud, the tester's opinion in test mode. */
export function AnswerStep() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const navigate = useNavigate();
  const online = useOnline();
  const {
    photo,
    crop,
    message,
    gouvernorat,
    context,
    setContext,
    submission,
    submit,
    answer,
    setAnswer,
    reset,
    queuedFrom,
  } = useDiagnosis();
  const cultures = useCultures();
  const sent = useRef<number | null>(null);
  const [pending, setPendingState] = useState<Pending | null>(null);

  const run = useMutation({
    mutationFn: () => api.diagnose(diagnoseForm(lang)),
    onSuccess: (a) => {
      setAnswer(a);
      void saveAnswer(a, useDiagnosis.getState().crop); // text only, on this device
    },
  });
  const { mutate } = run;

  // one request per submission ("Analyser", "Relancer", retry); after a reload the answer is asked again. Without
  // network nothing is sent: the farmer is told at once and can put the photo aside.
  const [offlineAt, setOfflineAt] = useState<number | null>(null);
  useEffect(() => {
    if (!answer && sent.current !== submission) {
      sent.current = submission;
      if (!navigator.onLine) {
        setOfflineAt(submission);
        return;
      }
      setOfflineAt(null);
      mutate();
    }
  }, [answer, submission, mutate]);

  useEffect(() => {
    void getPending().then(setPendingState);
  }, [submission]);

  const offline = offlineAt === submission && !run.isPending;
  const error = run.isError
    ? describeError(run.error, t)
    : offline
      ? { kind: "network" as const, text: t("error.network") }
      : null;
  const noNetwork = offline || run.error instanceof NetworkError || (run.isError && !online);

  async function putAside() {
    if (!photo || !crop) return;
    const p: Pending = {
      date: new Date().toISOString(),
      photo,
      crop,
      message,
      gouvernorat,
      context,
      langue: lang,
    };
    if (await setPending(p)) setPendingState(p);
  }

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

      {error && !pending && (
        <Alert
          tone="danger"
          title={t("error.title")}
          action={
            <div className="flex flex-wrap gap-2">
              {error.kind === "photo" ? (
                <Button variant="secondary" icon={Camera} onClick={() => navigate(STEP_PATH.photo)}>
                  {t("crop.retake")}
                </Button>
              ) : (
                <Button variant="secondary" icon={RotateCcw} onClick={submit}>
                  {t("common.retry")}
                </Button>
              )}
              {noNetwork && (
                <Button variant="secondary" icon={Clock} onClick={() => void putAside()}>
                  {t("queue.accept")}
                </Button>
              )}
            </div>
          }
        >
          {error.text}
          {noNetwork && <p className="mt-1">{t("queue.offer")}</p>}
        </Alert>
      )}

      {pending && !answer && (
        <Alert
          tone="info"
          icon={Clock}
          action={
            <Button
              variant="secondary"
              icon={X}
              onClick={() => void clearPending().then(() => setPendingState(null))}
            >
              {t("queue.cancel")}
            </Button>
          }
        >
          {t("queue.waiting", { date: formatDate(pending.date, lang) })}
        </Alert>
      )}

      {answer && queuedFrom && (
        <Alert tone="info" icon={Clock}>
          {t("queue.sent", { date: formatDate(queuedFrom, lang) })}
        </Alert>
      )}
      {answer && (
        <AnswerView
          answer={answer}
          cropLabel={cropName(crop, cultures.data, lang)}
          pageLang={lang}
          onOtherLang={submit}
          onRetake={() => navigate(STEP_PATH.photo)}
          refine={<RefineFields answer={answer} value={context} onChange={setContext} onSubmit={submit} />}
        />
      )}
    </StepPage>
  );
}

function RefineFields({
  answer,
  value,
  onChange,
  onSubmit,
}: {
  answer: DiagnoseAnswer;
  value: Parameters<typeof ContextFields>[0]["value"];
  onChange: Parameters<typeof ContextFields>[0]["onChange"];
  onSubmit: () => void;
}) {
  const { t } = useTranslation();
  const asked = (answer.questions_contexte ?? []).filter((f): f is ContextField =>
    (CONTEXT_FIELDS as string[]).includes(f),
  );
  if (!asked.length) return null;
  return (
    <div className="space-y-4">
      <ContextFields fields={asked} value={value} onChange={onChange} />
      <Button icon={RotateCcw} block onClick={onSubmit}>
        {t("answer.refine")}
      </Button>
    </div>
  );
}

/** The cards of an answer (also used by the history, with `old` set: the date is said, it is never shown as new). */
export function AnswerView({
  answer,
  cropLabel,
  pageLang,
  onOtherLang,
  onRetake,
  refine,
}: {
  answer: DiagnoseAnswer;
  cropLabel: string;
  pageLang: Lang;
  onOtherLang?: () => void;
  onRetake?: () => void;
  refine?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const cards = visibleCards(answer);
  const reliable = isReliable(answer);
  return (
    <div aria-live="polite" className="space-y-4">
      {answer.langue !== pageLang && onOtherLang && (
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
      {!reliable && answer.issue !== "autre_photo" && <Alert tone="warning">{t("cards.notReliable")}</Alert>}
      {cards.map((card, i) =>
        card.type === "affiner" ? (
          refine ? (
            <Card key={i} title={t("answer.refineTitle")} icon={SlidersHorizontal} tone="warning">
              <p>{card.titre}</p>
              {refine}
            </Card>
          ) : null
        ) : (
          <AnswerCardView key={i} card={card} answer={answer} cropLabel={cropLabel} />
        ),
      )}
      {answer.issue === "autre_photo" && onRetake && (
        <Button variant="secondary" icon={Camera} block onClick={onRetake}>
          {t("answer.retakePhoto")}
        </Button>
      )}
      <TraceView answer={answer} />
      <AnswerActions answer={answer} />
      {answer.journal_id && <FeedbackCard journalId={answer.journal_id} />}
    </div>
  );
}

import { useMutation } from "@tanstack/react-query";
import { MessageSquareHeart, Send } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/api/client";
import { useCultures } from "@/api/queries";
import { Alert, Button, Card, Chip } from "@/components/ui";
import type { Lang } from "@/lib/i18n";
import { describeError } from "../diagnosis/errors";

const VERDICTS = ["correct", "partiel", "faux"] as const;
type Verdict = (typeof VERDICTS)[number];

/** Test mode only (the answer has a journal_id): the tester says if the diagnosis is right, the true crop and
 * problem, a comment, and whether the photo may be kept. Nothing is sent before "Envoyer": the consent can be given
 * whatever the verdict (bug B1 of the first app). */
export function FeedbackCard({ journalId }: { journalId: string }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const cultures = useCultures();
  const ids = { crop: useId(), problem: useId(), comment: useId(), keep: useId() };
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [trueCrop, setTrueCrop] = useState("");
  const [problem, setProblem] = useState("");
  const [comment, setComment] = useState("");
  const [keep, setKeep] = useState(false);
  const [missing, setMissing] = useState(false);
  const send = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("journal_id", journalId);
      form.append("verdict", verdict ?? "");
      form.append("vraie_culture", trueCrop);
      form.append("vrai_probleme", problem.trim());
      form.append("commentaire", comment.trim());
      form.append("garder_photo", keep ? "oui" : "non");
      return api.feedback(form);
    },
  });

  if (send.isSuccess) return <Alert tone="success" title={t("test.thanks")} />;

  return (
    <Card title={t("test.title")} icon={MessageSquareHeart} tone="warning" className="print:hidden">
      <fieldset className="space-y-2">
        <legend className="font-semibold">{t("test.question")}</legend>
        <div className="flex flex-wrap gap-2">
          {VERDICTS.map((v) => (
            <Chip key={v} selected={verdict === v} onSelectedChange={() => setVerdict(v)}>
              {t(`test.${v}`)}
            </Chip>
          ))}
        </div>
      </fieldset>
      {verdict && verdict !== "correct" && (
        <>
          <div className="space-y-1">
            <label htmlFor={ids.crop} className="block font-semibold">
              {t("test.trueCrop")}
            </label>
            <select
              id={ids.crop}
              value={trueCrop}
              onChange={(e) => setTrueCrop(e.target.value)}
              className="min-h-touch w-full rounded-xl border-2 border-border bg-surface px-3 text-base"
            >
              <option value="">{t("test.trueCropNone")}</option>
              {(cultures.data ?? []).map((c) => (
                <option key={c.code} value={c.code}>
                  {c[lang]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor={ids.problem} className="block font-semibold">
              {t("test.trueProblem")}
            </label>
            <input
              id={ids.problem}
              value={problem}
              maxLength={300}
              placeholder={t("test.trueProblemPh")}
              onChange={(e) => setProblem(e.target.value)}
              className="min-h-touch w-full rounded-xl border-2 border-border bg-surface px-3 text-base"
            />
          </div>
        </>
      )}
      <div className="space-y-1">
        <label htmlFor={ids.comment} className="block font-semibold">
          {t("test.comment")}
        </label>
        <textarea
          id={ids.comment}
          rows={2}
          value={comment}
          maxLength={300}
          onChange={(e) => setComment(e.target.value)}
          className="w-full rounded-xl border-2 border-border bg-surface p-3 text-base"
        />
      </div>
      <label htmlFor={ids.keep} className="flex min-h-touch cursor-pointer items-start gap-3">
        <input
          id={ids.keep}
          type="checkbox"
          checked={keep}
          onChange={(e) => setKeep(e.target.checked)}
          className="mt-1 size-6 shrink-0 accent-[rgb(var(--primary))]"
        />
        <span>{t("test.keep")}</span>
      </label>
      {missing && !verdict && <Alert tone="warning">{t("test.chooseFirst")}</Alert>}
      {send.isError && <Alert tone="danger">{describeError(send.error, t).text}</Alert>}
      <Button
        icon={Send}
        block
        loading={send.isPending}
        onClick={() => {
          if (!verdict) {
            setMissing(true);
            return;
          }
          send.mutate();
        }}
      >
        {t("test.send")}
      </Button>
    </Card>
  );
}

import { ArrowLeft, Clock, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DiagnoseAnswer } from "@/api/client";
import { useCultures } from "@/api/queries";
import { Alert, BottomSheet, Button, Card, ConfidenceBadge, useToast } from "@/components/ui";
import { AnswerView } from "@/features/diagnosis/AnswerStep";
import { cropName } from "@/features/diagnosis/crops";
import { clearHistory, listHistory, type HistoryEntry } from "@/features/history/history";
import { formatDate } from "@/lib/format";
import type { Lang } from "@/lib/i18n";

/** The last answers kept on this phone (text only). An old answer is always shown with its date, never as new. */
export default function History() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const toast = useToast();
  const cultures = useCultures();
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const [open, setOpen] = useState<HistoryEntry | null>(null);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    void listHistory().then(setEntries);
  }, []);

  if (open) {
    const answer = {
      issue: open.issue,
      texte: open.texte,
      langue: open.langue,
      cartes: open.cartes,
      diagnostic: open.niveau ? { niveau: open.niveau, fiable: open.issue === "conseil" } : null,
      trace: [],
      duree_s: 0,
      questions_contexte: [],
    } as unknown as DiagnoseAnswer;
    return (
      <div className="space-y-4">
        <Button variant="secondary" icon={ArrowLeft} mirrorIcon onClick={() => setOpen(null)}>
          {t("history.back")}
        </Button>
        <Alert tone="info" icon={Clock}>
          {t("history.old", { date: formatDate(open.date, lang) })}
        </Alert>
        <AnswerView answer={answer} cropLabel={cropName(open.crop, cultures.data, lang)} pageLang={lang} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold sm:text-3xl">{t("history.title")}</h1>
      <p className="text-muted">{t("history.intro")}</p>
      {entries && entries.length === 0 && <Alert tone="info">{t("history.empty")}</Alert>}
      <ul className="space-y-3">
        {(entries ?? []).map((e) => (
          <li key={e.id}>
            <Card>
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{t("history.of", { date: formatDate(e.date, lang) })}</p>
                  <p className="text-muted">{cropName(e.crop, cultures.data, lang)}</p>
                </div>
                {e.niveau && <ConfidenceBadge level={e.niveau} />}
                <Button variant="secondary" onClick={() => setOpen(e)}>
                  {t("history.open")}
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>
      {entries && entries.length > 0 && (
        <Button variant="danger" icon={Trash2} onClick={() => setConfirm(true)}>
          {t("history.deleteAll")}
        </Button>
      )}
      <BottomSheet open={confirm} onOpenChange={setConfirm} title={t("history.deleteAll")}>
        <p className="mb-4">{t("history.confirm")}</p>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => setConfirm(false)}>
            {t("nav.back")}
          </Button>
          <Button
            variant="danger"
            icon={Trash2}
            block
            onClick={() => {
              void clearHistory().then(() => {
                setEntries([]);
                setConfirm(false);
                toast.show(t("history.deleted"), "success");
              });
            }}
          >
            {t("history.deleteAll")}
          </Button>
        </div>
      </BottomSheet>
    </div>
  );
}

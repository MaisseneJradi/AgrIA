import { Printer, Share2, Volume2, VolumeX, Workflow } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DiagnoseAnswer } from "@/api/client";
import { Button, useToast } from "@/components/ui";

/** "How AgrIA decided": the trace of the agents (who, what, how long), folded by default. */
export function TraceView({ answer }: { answer: DiagnoseAnswer }) {
  const { t } = useTranslation();
  if (!answer.trace.length) return null;
  return (
    <details className="rounded-card border border-border bg-surface p-4 shadow-card print:hidden">
      <summary className="flex min-h-touch cursor-pointer items-center gap-3 font-display text-lg font-semibold">
        <Workflow className="size-5 shrink-0" aria-hidden="true" />
        {t("cards.traceTitle")}
      </summary>
      <p className="mt-2 text-muted">{t("cards.traceIntro")}</p>
      <ol className="mt-3 space-y-2">
        {answer.trace.map((s, i) => (
          <li key={i} className="flex gap-3 border-s-2 border-border ps-3">
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{s.agent}</p>
              <p className="break-words text-sm text-muted" lang="fr" dir="ltr">
                {s.action}
              </p>
            </div>
            <span className="shrink-0 text-sm text-muted" dir="ltr">
              {t("cards.ms", { ms: s.duree_ms })}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-sm text-muted">{t("cards.traceTotal", { s: answer.duree_s })}</p>
    </details>
  );
}

function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

/** Share (WhatsApp...) or copy, print / PDF, read aloud: always the text of the API, unchanged. */
export function AnswerActions({ answer }: { answer: DiagnoseAnswer }) {
  const { t } = useTranslation();
  const toast = useToast();
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => (canSpeak() ? window.speechSynthesis.cancel() : undefined), []);

  async function share() {
    const text = answer.texte;
    if (navigator.share) {
      try {
        await navigator.share({ title: t("actions.shareTitle"), text });
        return;
      } catch {
        /* cancelled, or not allowed: copy instead */
      }
    }
    try {
      await navigator.clipboard.writeText(text);
      toast.show(t("actions.copied"), "success");
    } catch {
      toast.show(t("actions.copyFailed"));
    }
  }

  function read() {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const u = new SpeechSynthesisUtterance(answer.texte);
    u.lang = answer.langue === "ar" ? "ar" : "fr-FR";
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
    setSpeaking(true);
  }

  return (
    <div className="flex flex-wrap gap-2 print:hidden">
      <Button variant="secondary" icon={Share2} onClick={() => void share()}>
        {t("actions.share")}
      </Button>
      <Button variant="secondary" icon={Printer} onClick={() => window.print()}>
        {t("actions.print")}
      </Button>
      {canSpeak() && (
        <Button
          variant="secondary"
          icon={speaking ? VolumeX : Volume2}
          aria-pressed={speaking}
          onClick={read}
        >
          {speaking ? t("actions.stopRead") : t("actions.read")}
        </Button>
      )}
    </div>
  );
}

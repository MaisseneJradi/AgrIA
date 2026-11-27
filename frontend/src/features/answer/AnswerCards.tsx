import {
  AlertTriangle,
  BookOpen,
  Camera,
  CircleHelp,
  Droplets,
  ExternalLink,
  FlaskConical,
  HeartPulse,
  Info,
  Landmark,
  Leaf,
  ListChecks,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  SprayCan,
  Sprout,
  Store,
  Ruler,
  Ban,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { AnswerCard, CardLine, CardProduct, DiagnoseAnswer } from "@/api/client";
import { Card, ConfidenceBadge, type CardTone } from "@/components/ui";
import { cn } from "@/lib/cn";
import { AnswerText } from "./AnswerText";

type CardType = AnswerCard["type"];

const LOOK: Partial<Record<CardType, { icon: LucideIcon; tone?: CardTone }>> = {
  autre_photo: { icon: Camera, tone: "warning" },
  doute: { icon: CircleHelp, tone: "warning" },
  pistes: { icon: ListChecks, tone: "warning" },
  questions: { icon: CircleHelp, tone: "warning" },
  diagnostic: { icon: Leaf, tone: "success" },
  sain: { icon: HeartPulse, tone: "success" },
  hypothese: { icon: CircleHelp, tone: "warning" },
  crda: { icon: Landmark, tone: "danger" },
  traitements: { icon: SprayCan },
  securite: { icon: ShieldCheck, tone: "warning" },
  rotation: { icon: RefreshCw },
  ecartes: { icon: Ban },
  aucun_produit: { icon: Ban, tone: "warning" },
  engrais: { icon: FlaskConical },
  eau: { icon: Droplets },
  prevention: { icon: Sprout, tone: "success" },
  conseils: { icon: BookOpen },
  sources: { icon: BookOpen },
  a_savoir: { icon: AlertTriangle, tone: "warning" },
  texte: { icon: ScrollText },
};

const ROLE_ICON: Record<CardLine["role"], LucideIcon> = {
  produit: SprayCan,
  dose_pratique: Ruler,
  lmr: Info,
  boutique: Store,
  boutique_absente: Store,
  pourquoi: Info,
};

function Text({ text, lang }: { text: string; lang: "fr" | "ar" }) {
  return <AnswerText text={text} lang={lang} />;
}

function ProductCard({
  product,
  index,
  total,
  lang,
}: {
  product: CardProduct;
  index: number;
  total: number;
  lang: "fr" | "ar";
}) {
  const { t } = useTranslation();
  return (
    <article
      aria-label={t("cards.product", { n: index + 1, total })}
      className="space-y-3 rounded-xl border-2 border-border bg-bg p-3"
    >
      <h3 className="flex items-center gap-2 font-sans text-lg font-bold" lang={lang} dir="auto">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-sm text-on-primary">
          {index + 1}
        </span>
        <bdi>{product.nom}</bdi>
      </h3>
      <ul className="space-y-2">
        {product.lignes.map((line, i) => {
          const Icon = ROLE_ICON[line.role];
          return (
            <li key={i} className={cn("flex gap-3", line.role === "produit" && "font-semibold")}>
              <Icon className="mt-1 size-5 shrink-0 text-muted" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <span className="sr-only">{t(`cards.role.${line.role}`)}: </span>
                <Text text={line.texte} lang={lang} />
                {line.role === "boutique" && line.url && (
                  <a
                    href={line.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex min-h-touch items-center gap-2 rounded-xl border-2 border-border px-4 font-semibold"
                  >
                    <Store className="size-5" aria-hidden="true" />
                    {t("cards.openShop")}
                    <ExternalLink className="size-4 rtl:-scale-x-100" aria-hidden="true" />
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </article>
  );
}

/** One card of the answer: its words exactly as the API wrote them. */
export function AnswerCardView({
  card,
  answer,
  cropLabel,
  extra,
}: {
  card: AnswerCard;
  answer: DiagnoseAnswer;
  cropLabel?: string;
  extra?: ReactNode;
}) {
  const { t } = useTranslation();
  const lang = answer.langue;
  const look = LOOK[card.type] ?? { icon: Info };
  if (card.type === "fin") {
    return (
      <p className="flex gap-2 px-1 text-muted">
        <Info className="mt-1 size-5 shrink-0" aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <Text text={card.texte} lang={lang} />
        </span>
      </p>
    );
  }
  const isDiagnosis = ["diagnostic", "sain", "hypothese", "doute"].includes(card.type);
  const niveau = answer.diagnostic?.niveau;
  return (
    <Card
      title={t(`cards.${card.type === "texte" ? "texte" : card.type}`)}
      icon={look.icon}
      tone={look.tone}
      actions={
        isDiagnosis && niveau ? (
          <ConfidenceBadge level={niveau} className="hidden sm:inline-flex" />
        ) : undefined
      }
    >
      {isDiagnosis && (niveau || cropLabel) && (
        <div className="flex flex-wrap items-center gap-2">
          {niveau && <ConfidenceBadge level={niveau} className="sm:hidden" />}
          {cropLabel && (
            <span className="rounded-full bg-surface-2 px-3 py-1 text-sm font-semibold">{cropLabel}</span>
          )}
        </div>
      )}
      {card.produits ? (
        <>
          {card.titre && <Text text={card.titre} lang={lang} />}
          <div className="space-y-3">
            {card.produits.map((p, i) => (
              <ProductCard key={p.nom} product={p} index={i} total={card.produits?.length ?? 0} lang={lang} />
            ))}
          </div>
        </>
      ) : card.citations ? (
        <>
          <Text text={card.titre ?? ""} lang={lang} />
          <ul className="list-disc space-y-2 ps-5">
            {card.citations.map((c, i) => (
              <li key={i}>
                <Text text={c} lang={lang} />
              </li>
            ))}
          </ul>
          {card.sources?.map((s, i) => (
            <p key={i} className="text-sm text-muted">
              <Text text={s} lang={lang} />
            </p>
          ))}
        </>
      ) : card.elements ? (
        <>
          <Text text={card.titre ?? ""} lang={lang} />
          <ul className="list-disc space-y-2 ps-5">
            {card.elements.map((e, i) => (
              <li key={i}>
                <Text text={e} lang={lang} />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <Text text={card.texte} lang={lang} />
      )}
      {extra}
    </Card>
  );
}

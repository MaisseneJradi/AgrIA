import {
  Camera,
  Citrus,
  Droplets,
  Image,
  Leaf,
  SprayCan,
  Store,
  Trash2,
  ArrowRight,
  Send,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { I18nextProvider, useTranslation } from "react-i18next";
import {
  Alert,
  BottomSheet,
  Button,
  Card,
  Chip,
  ConfidenceBadge,
  LanguageSwitch,
  SkeletonBlock,
  Stepper,
  useToast,
} from "@/components/ui";
import { cn } from "@/lib/cn";
import i18n, { type Lang } from "@/lib/i18n";

/** Development only (excluded from the production build): every component in French and Arabic, light and dark,
 * side by side. Each panel has its own language (a copy of i18n), its own dir and lang, and its own theme class. */
export default function Styleguide() {
  const { t } = useTranslation();
  const panels: Array<{ lang: Lang; dark: boolean }> = [
    { lang: "fr", dark: false },
    { lang: "ar", dark: false },
    { lang: "fr", dark: true },
    { lang: "ar", dark: true },
  ];
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">{t("styleguide.title")}</h1>
        <p className="text-muted">{t("styleguide.intro")}</p>
        <LanguageSwitch />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        {panels.map((p) => (
          <Panel key={`${p.lang}-${p.dark}`} {...p} />
        ))}
      </div>
    </div>
  );
}

function Panel({ lang, dark }: { lang: Lang; dark: boolean }) {
  const local = useMemo(() => i18n.cloneInstance({ lng: lang }), [lang]);
  return (
    <I18nextProvider i18n={local}>
      <div
        lang={lang}
        dir={lang === "ar" ? "rtl" : "ltr"}
        data-testid={`panel-${lang}-${dark ? "dark" : "light"}`}
        className={cn(dark ? "dark" : "light", "rounded-card bg-bg p-4 text-text ring-1 ring-border")}
      >
        <p className="mb-4 font-mono text-sm text-muted" dir="ltr">
          {lang.toUpperCase()} · {dark ? "dark" : "light"}
        </p>
        <Showcase />
      </div>
    </I18nextProvider>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-6 space-y-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Showcase() {
  const { t } = useTranslation();
  const toast = useToast();
  const [crop, setCrop] = useState("tomato");
  const [sheet, setSheet] = useState(false);
  const steps = (["photo", "crop", "context", "answer"] as const).map((id) => ({
    id,
    label: t(`steps.${id}`),
  }));
  return (
    <div>
      <Section title={t("styleguide.buttons")}>
        <div className="flex flex-wrap gap-2">
          <Button icon={Camera}>{t("styleguide.takePhoto")}</Button>
          <Button variant="secondary" icon={Image}>
            {t("styleguide.gallery")}
          </Button>
          <Button variant="ghost" iconEnd={ArrowRight} mirrorIcon>
            {t("styleguide.next")}
          </Button>
          <Button variant="danger" icon={Trash2}>
            {t("styleguide.delete")}
          </Button>
          <Button loading>{t("styleguide.send")}</Button>
          <Button disabled icon={Send}>
            {t("styleguide.disabled")}
          </Button>
        </div>
      </Section>

      <Section title={t("styleguide.chips")}>
        <div className="flex flex-wrap gap-2">
          {[
            { id: "tomato", icon: Leaf },
            { id: "olive", icon: Leaf },
            { id: "citrus", icon: Citrus },
          ].map(({ id, icon }) => (
            <Chip key={id} icon={icon} selected={crop === id} onSelectedChange={() => setCrop(id)}>
              {t(`styleguide.${id}`)}
            </Chip>
          ))}
        </div>
      </Section>

      <Section title={t("styleguide.confidence")}>
        <div className="flex flex-wrap gap-2">
          <ConfidenceBadge level="sur" />
          <ConfidenceBadge level="probable" />
          <ConfidenceBadge level="incertain" />
        </div>
      </Section>

      <Section title={t("styleguide.stepper")}>
        <Stepper steps={steps} current={1} />
      </Section>

      <Section title={t("styleguide.cards")}>
        <Card title={t("styleguide.cardTitle")} icon={Leaf} actions={<ConfidenceBadge level="sur" />}>
          <p>{t("styleguide.cardBody")}</p>
        </Card>
        <Card title="Score 250 EC" icon={SprayCan} level={3} tone="warning">
          <p>{t("styleguide.doseExample")}</p>
        </Card>
        <Card title={t("styleguide.sheetTitle")} icon={Droplets} level={3} tone="success">
          <p className="flex items-center gap-2">
            <Store className="size-5" aria-hidden="true" />
            agrishop.tn
          </p>
        </Card>
      </Section>

      <Section title={t("styleguide.alerts")}>
        <Alert tone="info" title={t("styleguide.infoTitle")}>
          {t("styleguide.infoBody")}
        </Alert>
        <Alert tone="success" title={t("styleguide.successTitle")} onDismiss={() => undefined}>
          {t("styleguide.successBody")}
        </Alert>
        <Alert tone="warning" title={t("styleguide.warningTitle")}>
          {t("styleguide.warningBody")}
        </Alert>
        <Alert
          tone="danger"
          title={t("styleguide.dangerTitle")}
          action={<Button variant="secondary">{t("common.retry")}</Button>}
        >
          {t("styleguide.dangerBody")}
        </Alert>
      </Section>

      <Section title={t("styleguide.skeleton")}>
        <SkeletonBlock lines={3} />
      </Section>

      <Section title={`${t("styleguide.sheet")} · ${t("styleguide.toast")}`}>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setSheet(true)}>
            {t("styleguide.openSheet")}
          </Button>
          <Button variant="secondary" onClick={() => toast.show(t("styleguide.toastText"), "success")}>
            {t("styleguide.showToast")}
          </Button>
        </div>
        <BottomSheet open={sheet} onOpenChange={setSheet} title={t("styleguide.sheetTitle")}>
          <p>{t("styleguide.sheetBody")}</p>
        </BottomSheet>
      </Section>
    </div>
  );
}

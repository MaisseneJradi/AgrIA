import { BadgeCheck, CircleAlert, Landmark, Lock, ScrollText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui";

/** What AgrIA can and cannot do, privacy, the label, the CRDA (lazy-loaded page). */
export default function About() {
  const { t } = useTranslation();
  const sections = [
    {
      title: "about.whatTitle",
      icon: BadgeCheck,
      tone: "success" as const,
      items: ["about.what1", "about.what2", "about.what3"],
    },
    {
      title: "about.limitsTitle",
      icon: CircleAlert,
      tone: "warning" as const,
      items: ["about.limit1", "about.limit2", "about.limit3"],
    },
    { title: "about.labelTitle", icon: ScrollText, tone: "warning" as const, items: ["about.label"] },
    { title: "about.crdaTitle", icon: Landmark, tone: "default" as const, items: ["about.crda"] },
    {
      title: "about.privacyTitle",
      icon: Lock,
      tone: "default" as const,
      items: ["about.privacy1", "about.privacy2", "about.privacy3", "about.privacy4"],
    },
  ];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold sm:text-3xl">{t("about.title")}</h1>
      {sections.map((s) => (
        <Card key={s.title} title={t(s.title)} icon={s.icon} tone={s.tone}>
          {s.items.length === 1 ? (
            <p>{t(s.items[0] ?? "")}</p>
          ) : (
            <ul className="list-disc space-y-2 ps-5">
              {s.items.map((k) => (
                <li key={k}>{t(k)}</li>
              ))}
            </ul>
          )}
        </Card>
      ))}
    </div>
  );
}

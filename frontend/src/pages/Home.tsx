import { Camera } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Alert, Card } from "@/components/ui";

/** Step 1 of the React plan: the shell only. The farmer flow (photo, crop, context, answer) comes at step 2. */
export function Home() {
  const { t } = useTranslation();
  return (
    <Card title={t("app.name")} icon={Camera}>
      <Alert tone="info">{t("app.comingSoon")}</Alert>
    </Card>
  );
}

import { useQuery } from "@tanstack/react-query";
import { Download, KeyRound, LogOut } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, type JournalRow } from "@/api/client";
import { useCultures } from "@/api/queries";
import { Alert, Button, Card, SkeletonBlock } from "@/components/ui";
import { cropName } from "@/features/diagnosis/crops";
import { describeError } from "@/features/diagnosis/errors";
import { formatDate } from "@/lib/format";
import type { Lang } from "@/lib/i18n";

const TOKEN_KEY = "agria-admin";

function savedToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Test mode administration (lazy-loaded): the analyses of the journal, filters, accuracy per crop as computed by
 * the server, CSV export for the evaluation scripts. The token is checked by the server (AGRIA_ADMIN_TOKEN). */
export default function AdminTest() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language as Lang;
  const cultures = useCultures();
  const [token, setToken] = useState(savedToken);
  const [draft, setDraft] = useState("");
  const [filters, setFilters] = useState({ crop: "", gov: "", verdict: "" });
  const ids = { token: useId(), crop: useId(), gov: useId(), verdict: useId() };
  const journal = useQuery({
    queryKey: ["admin", token],
    queryFn: () => api.adminJournal(token),
    enabled: !!token,
    retry: false,
  });

  const rows = useMemo(
    () =>
      (journal.data?.analyses ?? []).filter(
        (r: JournalRow) =>
          (!filters.crop || r.culture === filters.crop) &&
          (!filters.gov || r.gouvernorat === filters.gov) &&
          (!filters.verdict || (filters.verdict === "none" ? !r.verdict : r.verdict === filters.verdict)),
      ),
    [journal.data, filters],
  );
  const govs = Array.from(new Set((journal.data?.analyses ?? []).map((r) => r.gouvernorat).filter(Boolean)));

  async function exportCsv() {
    const blob = await api.adminCsv(token);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "journal_agria.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!token || (journal.error instanceof ApiError && journal.error.status === 401)) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">{t("admin.title")}</h1>
        {token && <Alert tone="danger">{t("admin.badToken")}</Alert>}
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            try {
              sessionStorage.setItem(TOKEN_KEY, draft);
            } catch {
              /* kept in memory only */
            }
            setToken(draft);
          }}
        >
          <label htmlFor={ids.token} className="block font-semibold">
            {t("admin.token")}
          </label>
          <input
            id={ids.token}
            type="password"
            autoComplete="off"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="min-h-touch w-full rounded-xl border-2 border-border bg-surface px-3 text-base"
          />
          <p className="text-sm text-muted">{t("admin.tokenHelp")}</p>
          <Button type="submit" icon={KeyRound} disabled={!draft}>
            {t("admin.signIn")}
          </Button>
        </form>
      </div>
    );
  }

  const select = "min-h-touch w-full rounded-xl border-2 border-border bg-surface px-3 text-base";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="flex-1 text-2xl font-bold">{t("admin.title")}</h1>
        <Button
          variant="ghost"
          icon={LogOut}
          onClick={() => {
            sessionStorage.removeItem(TOKEN_KEY);
            setToken("");
          }}
        >
          {t("admin.signOut")}
        </Button>
      </div>
      {journal.isPending && <SkeletonBlock lines={5} />}
      {journal.error instanceof ApiError && journal.error.status === 404 && (
        <Alert tone="warning">{t("admin.off")}</Alert>
      )}
      {journal.isError &&
        !(journal.error instanceof ApiError && [401, 404].includes(journal.error.status)) && (
          <Alert tone="danger">{describeError(journal.error, t).text}</Alert>
        )}
      {journal.data && (
        <>
          <Card title={t("admin.accuracy")} level={2}>
            <div className="overflow-x-auto">
              <table className="w-full text-start">
                <thead>
                  <tr className="border-b border-border text-sm text-muted">
                    <th className="p-2 text-start">{t("admin.crop")}</th>
                    <th className="p-2 text-end">{t("admin.analyses")}</th>
                    <th className="p-2 text-end">{t("admin.withFeedback")}</th>
                    <th className="p-2 text-end">{t("admin.precision")}</th>
                  </tr>
                </thead>
                <tbody>
                  {journal.data.par_culture.map((s) => (
                    <tr key={s.culture} className="border-b border-border">
                      <td className="p-2">{cropName(s.culture, cultures.data, lang)}</td>
                      <td className="p-2 text-end" dir="ltr">
                        {s.analyses}
                      </td>
                      <td className="p-2 text-end" dir="ltr">
                        {s.avec_avis}
                      </td>
                      <td className="p-2 text-end" dir="ltr">
                        {s.precision == null ? t("admin.none") : `${Math.round(s.precision * 100)} %`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title={t("admin.filters")} level={2}>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label htmlFor={ids.crop} className="mb-1 block text-sm font-semibold">
                  {t("admin.crop")}
                </label>
                <select
                  id={ids.crop}
                  className={select}
                  value={filters.crop}
                  onChange={(e) => setFilters({ ...filters, crop: e.target.value })}
                >
                  <option value="">{t("admin.allCrops")}</option>
                  {(cultures.data ?? []).map((c) => (
                    <option key={c.code} value={c.code}>
                      {c[lang]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={ids.gov} className="mb-1 block text-sm font-semibold">
                  {t("admin.gov")}
                </label>
                <select
                  id={ids.gov}
                  className={select}
                  value={filters.gov}
                  onChange={(e) => setFilters({ ...filters, gov: e.target.value })}
                >
                  <option value="">{t("admin.allGovs")}</option>
                  {govs.map((g) => (
                    <option key={g} value={g ?? ""}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={ids.verdict} className="mb-1 block text-sm font-semibold">
                  {t("admin.verdict")}
                </label>
                <select
                  id={ids.verdict}
                  className={select}
                  value={filters.verdict}
                  onChange={(e) => setFilters({ ...filters, verdict: e.target.value })}
                >
                  <option value="">{t("admin.allVerdicts")}</option>
                  <option value="correct">{t("test.correct")}</option>
                  <option value="partiel">{t("test.partiel")}</option>
                  <option value="faux">{t("test.faux")}</option>
                  <option value="none">{t("admin.noVerdict")}</option>
                </select>
              </div>
            </div>
            <Button variant="secondary" icon={Download} onClick={() => void exportCsv()}>
              {t("admin.export")}
            </Button>
          </Card>

          <Card title={t("admin.list", { n: rows.length })} level={2}>
            <ul className="divide-y divide-border">
              {rows.map((r) => (
                <li key={r.id} className="space-y-1 py-3">
                  <p className="text-sm text-muted">
                    {formatDate(r.date, lang)} · {cropName(r.culture, cultures.data, lang) || t("admin.none")}{" "}
                    · {r.gouvernorat ?? t("admin.none")}
                  </p>
                  <p className="font-semibold" lang="fr" dir="ltr">
                    {r.maladie ?? r.issue}
                  </p>
                  <p>
                    {t("admin.verdict")}: {r.verdict ? t(`test.${r.verdict}`) : t("admin.noVerdict")}
                    {r.vrai_probleme ? ` · ${r.vrai_probleme}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}

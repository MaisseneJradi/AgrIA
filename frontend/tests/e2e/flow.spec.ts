import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { API, jpegSize, mockApi, PHOTO, runFlow } from "./api";

// The farmer flow in Chrome on a phone (360x800), API mocked with REAL answers of the backend: the real photo
// pipeline of the browser runs (EXIF orientation, 1280 px, JPEG), what the app sends is checked, axe at each screen.

async function noSeriousAxe(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(
    r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
}

test("full flow in French: photo upright and reduced, crop confirmed, answer as cards", async ({ page }) => {
  const seen = await mockApi(page);
  await page.goto("/");
  await noSeriousAxe(page);
  await page.getByTestId("camera-input").setInputFiles(PHOTO);
  await expect(page.getByAltText("Votre photo")).toBeVisible();
  await page.getByRole("button", { name: "Continuer" }).click();

  await expect(page).toHaveURL(/\/culture$/);
  await expect(page.getByRole("button", { name: /Tomate/ })).toBeVisible();
  const sentPhoto = seen.identify[0];
  if (!sentPhoto) throw new Error("no photo sent");
  expect(jpegSize(sentPhoto)).toEqual({ width: 853, height: 1280 }); // EXIF 6 applied, longest side 1280
  expect(sentPhoto.length).toBeLessThan(readFileSync(PHOTO).length);
  await expect(page.getByRole("button", { name: "Continuer" })).toBeDisabled();
  await noSeriousAxe(page);
  await page.getByRole("button", { name: /Tomate/ }).click();
  await page.getByRole("button", { name: "Continuer" }).click();

  await expect(page).toHaveURL(/\/precisions$/);
  await page.getByRole("button", { name: /Choisir le gouvernorat/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Sfax" }).click();
  await page.getByRole("button", { name: "Marché local" }).click();
  await noSeriousAxe(page);
  await page.getByRole("button", { name: "Analyser la photo" }).click();

  await expect(page).toHaveURL(/\/reponse$/);
  await expect(page.getByRole("region", { name: "Diagnostic" })).toContainText("Alternariose");
  await expect(page.getByRole("region", { name: "Diagnostic" })).toContainText("Sûr");
  await expect(page.getByRole("article")).toHaveCount(3);
  await expect(page.getByRole("link", { name: "Voir la page du produit" })).toHaveCount(1);
  await expect(page.getByRole("region", { name: "Sécurité" })).toBeVisible();
  const form = seen.diagnose[0] ?? "";
  for (const [k, v] of [
    ["culture", "tomato"],
    ["langue", "fr"],
    ["gouvernorat", "Sfax"],
    ["market", "local"],
  ])
    expect(form).toContain(`name="${k}"\r\n\r\n${v}`);
  await noSeriousAxe(page);

  // the answer is kept in the history (text only), the back button goes to the previous step
  await page.goto("/historique");
  await expect(page.getByText(/Réponse du/)).toBeVisible();
  await noSeriousAxe(page);
  await page.goBack();
  await page.goBack();
  await expect(page).toHaveURL(/\/precisions$/);
  await page.reload();
  await expect(page.getByRole("button", { name: "Marché local" })).toHaveAttribute("aria-pressed", "true");
});

test("full flow in Arabic, right to left", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "العربية" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await runFlow(page, "ar");
  await expect(page.getByRole("region", { name: "التشخيص" })).toContainText("مؤكد");
  await expect(page.getByRole("region", { name: "المبيدات المصادق عليها" })).toBeVisible();
  await noSeriousAxe(page);
});

test("a photo that is not a plant is refused with a way back", async ({ page }) => {
  await mockApi(page, { identify: { feuille: false, photo_plante: false, routage: "other" } });
  await page.goto("/");
  await page.getByTestId("camera-input").setInputFiles(PHOTO);
  await page.getByRole("button", { name: "Continuer" }).click();
  await expect(page.getByText("Ce n'est pas une plante")).toBeVisible();
  await noSeriousAxe(page);
  await page.getByRole("button", { name: "Reprendre une photo" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("unreliable diagnosis: the questions only, no product", async ({ page }) => {
  await mockApi(page, { diagnose: (r) => r.fulfill({ json: API.question_fr }) });
  await page.goto("/");
  await runFlow(page);
  await expect(page.getByRole("region", { name: "Diagnostic incertain" })).toBeVisible();
  await expect(page.getByText(/aucun produit n'est conseillé avant confirmation/)).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Traitements homologués" })).toHaveCount(0);
  await noSeriousAxe(page);
});

test("network error on the analysis, then retry", async ({ page }) => {
  let fail = true;
  await mockApi(page, {
    diagnose: (r) => (fail ? r.abort("internetdisconnected") : r.fulfill({ json: API.conseil_fr })),
  });
  await page.goto("/");
  await runFlow(page);
  await expect(page.getByText(/Vérifiez votre connexion/)).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Réessayer" }).click();
  await expect(page.getByRole("region", { name: "Diagnostic" })).toBeVisible();
});

test("offline: the app says so, the photo waits and leaves when the network comes back", async ({
  page,
  context,
}) => {
  const seen = await mockApi(page);
  await page.goto("/");
  await page.getByTestId("camera-input").setInputFiles(PHOTO);
  await page.getByRole("button", { name: "Continuer" }).click();
  await page
    .getByRole("button", { name: /Tomate/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Continuer" }).click();
  await context.setOffline(true);
  await expect(page.getByText(/Pas de connexion\. Vérifiez le réseau/)).toBeVisible();
  await page.getByRole("button", { name: "Analyser la photo" }).click();
  await page.getByRole("button", { name: "Envoyer quand le réseau revient" }).click();
  await expect(page.getByText(/Photo en attente depuis le/)).toBeVisible();
  const before = seen.diagnose.length;
  await context.setOffline(false);
  await expect(page.getByText(/Votre photo mise en attente le/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Diagnostic" })).toBeVisible();
  expect(seen.diagnose.length).toBe(before + 1);
});

test("test mode: banner, then the tester's opinion with consent", async ({ page }) => {
  const seen = await mockApi(page, { testMode: true });
  await page.goto("/");
  await expect(page.getByText(/Mode test : vos analyses sont enregistrées/)).toBeVisible();
  await runFlow(page);
  const card = page.getByRole("region", { name: "Votre avis sur ce diagnostic" });
  await card.getByRole("button", { name: "Faux" }).click();
  await card.getByLabel("La vraie culture").selectOption("olive");
  await card.getByLabel(/Le vrai problème/).fill("œil de paon");
  await card.getByLabel(/J'accepte qu'AgrIA garde cette photo/).check();
  await noSeriousAxe(page);
  await card.getByRole("button", { name: "Envoyer mon avis" }).click();
  await expect(page.getByText("Merci, votre avis est enregistré.")).toBeVisible();
  const body = seen.feedback[0] ?? "";
  for (const [k, v] of [
    ["verdict", "faux"],
    ["vraie_culture", "olive"],
    ["vrai_probleme", "œil de paon"],
    ["garder_photo", "oui"],
  ])
    expect(body).toContain(`name="${k}"\r\n\r\n${v}`);
});

test("about page and admin page: no serious accessibility issue", async ({ page }) => {
  await mockApi(page);
  for (const path of ["/a-propos", "/admin/test", "/historique"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await noSeriousAxe(page);
  }
});

test("installable app: manifest, icons, service worker; the app opens offline", async ({ page, context }) => {
  await mockApi(page);
  await page.goto("/");
  const manifest = await page.locator('link[rel="manifest"]').getAttribute("href");
  expect(manifest).toBeTruthy();
  const m = await (await page.request.get(manifest ?? "")).json();
  expect(m.display).toBe("standalone");
  expect(m.icons.map((i: { sizes: string }) => i.sizes)).toEqual(
    expect.arrayContaining(["192x192", "512x512"]),
  );
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload(); // the service worker now controls the page
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Prenez une photo de la plante" })).toBeVisible();
  await expect(page.getByText(/Pas de connexion/)).toBeVisible();
  await context.setOffline(false);
});

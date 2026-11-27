import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";

// The farmer flow in Chrome on a phone, API mocked (page.route): the real photo pipeline of the browser runs
// (EXIF orientation, resize to 1280 px, JPEG), and what the app sends is checked.
const PHOTO = "tests/e2e/fixtures/feuille-exif6.jpg"; // 3000x2000 stored, EXIF 6: upright it is 2000x3000

const CULTURES = [
  { code: "tomato", fr: "Tomate", ar: "طماطم" },
  { code: "olive", fr: "Olivier", ar: "زيتون" },
  { code: "citrus", fr: "Agrumes", ar: "قوارص" },
];
const GOVS = [
  { fr: "Nabeul", ar: "نابل" },
  { fr: "Sfax", ar: "صفاقس" },
];
const IDENTIFY = {
  feuille: true,
  photo_plante: true,
  routage: "leaf",
  culture: "tomato",
  fr: "Tomate",
  ar: "طماطم",
  confiance: 0.96,
  sure: true,
  autre_plante: false,
  top3: [
    { code: "tomato", fr: "Tomate", confiance: 0.96 },
    { code: "olive", fr: "Olivier", confiance: 0.02 },
    { code: "citrus", fr: "Agrumes", confiance: 0.01 },
  ],
};
const answer = (langue: "fr" | "ar") => ({
  issue: "conseil",
  texte:
    langue === "fr"
      ? "Diagnostic : Alternariose (confiance 98 %).\n- Score 250 EC (Difenoconazole) : dose 0.5 l/ha ; délai avant récolte : 3 jours\n  https://www.agrishop.tn/store/category/Pesticides/Fongicides/score-250-ec/"
      : "التشخيص: اللفحة المبكرة.\n- Score 250 EC (Difenoconazole): الجرعة 0.5 l/ha",
  langue,
  diagnostic: { classe: "tomato__early_blight", nom: "Alternariose", confiance: 98, fiable: true },
  culture: { code: "tomato" },
  produits: [{ nom: "Score 250 EC", dose: "0.5 l/ha", dar_jours: 3 }],
  engrais: [],
  avertissements: [],
  questions: [],
  sources: [],
  verification: { valide: true, raisons: [], avertissements: [], produits_verifies: [] },
  contexte: {},
  questions_contexte: [],
  trace: [],
  duree_s: 0.3,
});

/** Width and height of a JPEG from its SOF marker. */
function jpegSize(buf: Buffer): { width: number; height: number } {
  let i = 2;
  while (i < buf.length) {
    const marker = buf[i + 1] ?? 0;
    const len = buf.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc3) return { height: buf.readUInt16BE(i + 5), width: buf.readUInt16BE(i + 7) };
    i += 2 + len;
  }
  throw new Error("no SOF");
}

/** The photo part of a multipart body. */
function photoOf(route: Route): Buffer {
  const body = route.request().postDataBuffer() ?? Buffer.alloc(0);
  const start = body.indexOf(Buffer.from([0xff, 0xd8]));
  const end = body.lastIndexOf(Buffer.from([0xff, 0xd9]));
  return body.subarray(start, end + 2);
}

async function mockApi(page: Page, opts: { identify?: object; diagnose?: (route: Route) => Promise<void> } = {}) {
  const seen: { identify: Buffer[]; diagnose: string[] } = { identify: [], diagnose: [] };
  await page.route("**/cultures", (r) => r.fulfill({ json: CULTURES }));
  await page.route("**/gouvernorats", (r) => r.fulfill({ json: GOVS }));
  await page.route("**/identify", async (r) => {
    seen.identify.push(photoOf(r));
    await r.fulfill({ json: opts.identify ?? IDENTIFY });
  });
  await page.route("**/diagnose", async (r) => {
    seen.diagnose.push(r.request().postDataBuffer()?.toString("latin1") ?? "");
    if (opts.diagnose) return opts.diagnose(r);
    const lang = /name="langue"\r\n\r\nar/.test(seen.diagnose.at(-1) ?? "") ? "ar" : "fr";
    return r.fulfill({ json: answer(lang) });
  });
  return seen;
}

async function noSeriousAxe(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
}

test("full flow in French: the photo is turned upright and reduced, the form is what the farmer entered", async ({
  page,
}) => {
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
  // EXIF 6 applied (portrait), longest side 1280, a small JPEG
  expect(jpegSize(sentPhoto)).toEqual({ width: 853, height: 1280 });
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
  await expect(page.getByText(/Diagnostic : Alternariose/)).toBeVisible();
  await expect(page.getByRole("link", { name: /agrishop\.tn/ })).toBeVisible();
  const form = seen.diagnose[0] ?? "";
  for (const [k, v] of [
    ["culture", "tomato"],
    ["langue", "fr"],
    ["gouvernorat", "Sfax"],
    ["market", "local"],
  ])
    expect(form).toContain(`name="${k}"\r\n\r\n${v}`);
  await noSeriousAxe(page);

  // the phone's back button goes to the previous step; a reload keeps what was entered
  await page.goBack();
  await expect(page).toHaveURL(/\/precisions$/);
  await page.reload();
  await expect(page.getByRole("button", { name: /Sfax/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Marché local" })).toHaveAttribute("aria-pressed", "true");
});

test("full flow in Arabic, right to left", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "العربية" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByTestId("gallery-input").setInputFiles(PHOTO);
  await page.getByRole("button", { name: "متابعة" }).click();
  await page.getByRole("button", { name: /طماطم/ }).click();
  await page.getByRole("button", { name: "متابعة" }).click();
  await page.getByRole("button", { name: "حلّل الصورة" }).click();
  const text = page.getByText(/التشخيص: اللفحة المبكرة/);
  await expect(text).toBeVisible();
  await noSeriousAxe(page);
});

test("a photo that is not a plant is refused with a way back", async ({ page }) => {
  await mockApi(page, { identify: { feuille: false, photo_plante: false, routage: "other" } });
  await page.goto("/");
  await page.getByTestId("camera-input").setInputFiles(PHOTO);
  await page.getByRole("button", { name: "Continuer" }).click();
  await expect(page.getByText("Ce n'est pas une plante")).toBeVisible();
  await page.getByRole("button", { name: "Reprendre une photo" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("network error on the analysis, then retry", async ({ page }) => {
  let fail = true;
  await mockApi(page, {
    diagnose: (r) => (fail ? r.abort("internetdisconnected") : r.fulfill({ json: answer("fr") })),
  });
  await page.goto("/");
  await page.getByTestId("camera-input").setInputFiles(PHOTO);
  await page.getByRole("button", { name: "Continuer" }).click();
  await page.getByRole("button", { name: /Tomate/ }).click();
  await page.getByRole("button", { name: "Continuer" }).click();
  await page.getByRole("button", { name: "Analyser la photo" }).click();
  await expect(page.getByText(/Vérifiez votre connexion/)).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Réessayer" }).click();
  await expect(page.getByText(/Diagnostic : Alternariose/)).toBeVisible();
});

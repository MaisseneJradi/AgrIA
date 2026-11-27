// Mocked API for the end-to-end tests: the REAL answers of the backend (fixtures/api.json, written by the API on
// 27/11/2026). Records what the app sends.
import type { Page, Route } from "@playwright/test";
import { readFileSync } from "node:fs";

export const API = JSON.parse(readFileSync("tests/e2e/fixtures/api.json", "utf-8"));
export const PHOTO = "tests/e2e/fixtures/feuille-exif6.jpg"; // 3000x2000 stored, EXIF 6: upright it is 2000x3000

export interface Seen {
  identify: Buffer[];
  diagnose: string[];
  feedback: string[];
}

/** The photo part of a multipart body. */
export function photoOf(route: Route): Buffer {
  const body = route.request().postDataBuffer() ?? Buffer.alloc(0);
  const start = body.indexOf(Buffer.from([0xff, 0xd8]));
  const end = body.lastIndexOf(Buffer.from([0xff, 0xd9]));
  return body.subarray(start, end + 2);
}

/** Width and height of a JPEG from its SOF marker. */
export function jpegSize(buf: Buffer): { width: number; height: number } {
  let i = 2;
  while (i < buf.length) {
    const marker = buf[i + 1] ?? 0;
    const len = buf.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc3)
      return { height: buf.readUInt16BE(i + 5), width: buf.readUInt16BE(i + 7) };
    i += 2 + len;
  }
  throw new Error("no SOF");
}

export async function mockApi(
  page: Page,
  opts: {
    identify?: object;
    diagnose?: (route: Route, lang: "fr" | "ar") => Promise<void>;
    testMode?: boolean;
  } = {},
): Promise<Seen> {
  const seen: Seen = { identify: [], diagnose: [], feedback: [] };
  await page.route("**/cultures", (r) => r.fulfill({ json: API.cultures }));
  await page.route("**/gouvernorats", (r) => r.fulfill({ json: API.gouvernorats }));
  await page.route("**/health", (r) =>
    r.fulfill({
      json: { statut: "ok", modeles: [], device: "cpu", mode_test: !!opts.testMode, admin: false },
    }),
  );
  await page.route("**/identify", async (r) => {
    seen.identify.push(photoOf(r));
    await r.fulfill({ json: opts.identify ?? API.identify_tomate });
  });
  await page.route("**/diagnose", async (r) => {
    const body = r.request().postDataBuffer()?.toString("latin1") ?? "";
    seen.diagnose.push(body);
    const lang = /name="langue"\r\n\r\nar/.test(body) ? "ar" : "fr";
    if (opts.diagnose) return opts.diagnose(r, lang);
    const answer = lang === "ar" ? API.conseil_ar : API.conseil_fr;
    return r.fulfill({ json: opts.testMode ? { ...answer, journal_id: "20261127-120000-abcdef" } : answer });
  });
  await page.route("**/feedback", async (r) => {
    seen.feedback.push(r.request().postDataBuffer()?.toString("utf-8") ?? "");
    await r.fulfill({ json: { statut: "enregistré" } });
  });
  return seen;
}

export const T = {
  fr: { cont: "Continuer", analyse: "Analyser la photo", tomato: /Tomate/, olive: /Olivier/ },
  ar: { cont: "متابعة", analyse: "حلّل الصورة", tomato: /طماطم/, olive: /زيتون/ },
};

/** Photo -> tomato -> analysis, in a language. */
export async function runFlow(page: Page, lang: "fr" | "ar" = "fr") {
  const t = T[lang];
  await page.getByTestId("camera-input").setInputFiles(PHOTO);
  await page.getByRole("button", { name: t.cont }).click();
  await page.getByRole("button", { name: t.tomato }).first().click();
  await page.getByRole("button", { name: t.cont }).click();
  await page.getByRole("button", { name: t.analyse }).click();
}

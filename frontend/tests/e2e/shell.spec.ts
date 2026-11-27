import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Step 1: the shell of the app (header, language, theme) in French and Arabic, with no serious accessibility issue.
for (const lang of ["fr", "ar"] as const) {
  test(`shell in ${lang}: direction, language kept, no serious axe violation`, async ({ page }) => {
    await page.goto("/");
    if (lang === "ar") await page.getByRole("button", { name: "العربية" }).click();
    await expect(page.locator("html")).toHaveAttribute("dir", lang === "ar" ? "rtl" : "ltr");
    await expect(page.locator("html")).toHaveAttribute("lang", lang);
    await page.reload(); // the choice is kept on the device
    await expect(page.locator("html")).toHaveAttribute("lang", lang);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
}

test("dark theme kept after reload, and the style guide is not in the production build", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sombre" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.goto("/styleguide");
  await expect(page.getByRole("heading", { name: "Guide des composants" })).toHaveCount(0);
});

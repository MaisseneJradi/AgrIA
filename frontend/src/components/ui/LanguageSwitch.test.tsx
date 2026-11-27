import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { LANG_KEY } from "@/lib/i18n";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { LanguageSwitch } from "./LanguageSwitch";

describe.each(["fr", "ar"] as const)("LanguageSwitch (starting in %s)", (start) => {
  it("switches lang and dir on <html>, the texts, and keeps the choice on the device", async () => {
    const { container } = await renderIn(start, <LanguageSwitch />);
    const other = start === "fr" ? "ar" : "fr";
    const current = screen.getByRole("button", { name: start === "fr" ? "Français" : "العربية" });
    expect(current).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: other === "fr" ? "Français" : "العربية" }));
    expect(document.documentElement.lang).toBe(other);
    expect(document.documentElement.dir).toBe(other === "ar" ? "rtl" : "ltr");
    expect(localStorage.getItem(LANG_KEY)).toBe(other);
    // the group label is now in the other language
    expect(screen.getByRole("group", { name: other === "fr" ? "Langue" : "اللغة" })).toBeInTheDocument();
    expectLogicalDirectionOnly(container);
  });
});

import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { THEME_KEY } from "@/lib/theme";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { ThemeSwitch } from "./ThemeSwitch";

describe.each(["fr", "ar"] as const)("ThemeSwitch (%s)", (lang) => {
  it("dark, light and system: class on <html>, kept on the device", async () => {
    const { container } = await renderIn(lang, <ThemeSwitch />);
    const names = lang === "fr" ? ["Sombre", "Clair", "Comme le téléphone"] : ["داكن", "فاتح", "مثل الهاتف"];
    await userEvent.click(screen.getByRole("button", { name: names[0] }));
    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    await userEvent.click(screen.getByRole("button", { name: names[1] }));
    expect(document.documentElement).not.toHaveClass("dark");
    await userEvent.click(screen.getByRole("button", { name: names[2] }));
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    expect(screen.getByRole("button", { name: names[2] })).toHaveAttribute("aria-pressed", "true");
    expectLogicalDirectionOnly(container);
  });
});

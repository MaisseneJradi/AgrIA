import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ArrowRight, Camera } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { Button } from "./Button";

describe.each(["fr", "ar"] as const)("Button (%s)", (lang) => {
  it("is a 48 px target with an icon hidden from screen readers, and clicks", async () => {
    const onClick = vi.fn();
    const { container } = await renderIn(
      lang,
      <Button icon={Camera} onClick={onClick}>
        Photo
      </Button>,
    );
    const b = screen.getByRole("button", { name: "Photo" });
    expect(b).toHaveAttribute("type", "button");
    expect(b.className).toMatch(/min-h-touch/);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    await userEvent.click(b);
    expect(onClick).toHaveBeenCalledOnce();
    expect(document.documentElement.dir).toBe(lang === "ar" ? "rtl" : "ltr");
    expectLogicalDirectionOnly(container);
  });

  it("loading: disabled, aria-busy, no click", async () => {
    const onClick = vi.fn();
    await renderIn(
      lang,
      <Button loading onClick={onClick}>
        Envoyer
      </Button>,
    );
    const b = screen.getByRole("button", { name: "Envoyer" });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    await userEvent.click(b);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("mirrors a directional icon in right to left", async () => {
    const { container } = await renderIn(
      lang,
      <Button iconEnd={ArrowRight} mirrorIcon>
        Suivant
      </Button>,
    );
    expect(container.querySelector("svg")?.getAttribute("class")).toMatch(/rtl:-scale-x-100/);
  });
});

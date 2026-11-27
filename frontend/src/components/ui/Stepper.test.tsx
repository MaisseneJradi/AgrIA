import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { Stepper } from "./Stepper";

const STEPS = [
  { id: "photo", label: "Photo" },
  { id: "crop", label: "Culture" },
  { id: "context", label: "Précisions" },
  { id: "answer", label: "Réponse" },
];

describe.each(["fr", "ar"] as const)("Stepper (%s)", (lang) => {
  it("marks the current step and says where we are", async () => {
    const { container } = await renderIn(lang, <Stepper steps={STEPS} current={1} />);
    const nav = screen.getByRole("navigation", { name: lang === "fr" ? "Étapes" : "المراحل" });
    const items = within(nav).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items[1]).toHaveAttribute("aria-current", "step");
    expect(items[0]).not.toHaveAttribute("aria-current");
    expect(nav).toHaveTextContent(lang === "fr" ? "Étape 2 sur 4" : "المرحلة 2 من 4");
    // the step done is said to screen readers
    expect(items[0]).toHaveTextContent(lang === "fr" ? "terminée" : "منتهية");
    expectLogicalDirectionOnly(container);
  });
});

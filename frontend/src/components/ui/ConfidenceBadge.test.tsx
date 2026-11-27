import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { ConfidenceBadge } from "./ConfidenceBadge";

const WORDS = {
  fr: { sur: "Sûr", probable: "Probable", incertain: "Pas sûr" },
  ar: { sur: "مؤكد", probable: "محتمل", incertain: "غير مؤكد" },
};

describe.each(["fr", "ar"] as const)("ConfidenceBadge (%s)", (lang) => {
  it.each(["sur", "probable", "incertain"] as const)("level %s in words, never a number", async (level) => {
    const { container } = await renderIn(lang, <ConfidenceBadge level={level} />);
    expect(screen.getByText(WORDS[lang][level])).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\d|%/);
    expect(container.textContent).toContain(lang === "fr" ? "Fiabilité du diagnostic" : "موثوقية التشخيص");
    expectLogicalDirectionOnly(container);
  });
});

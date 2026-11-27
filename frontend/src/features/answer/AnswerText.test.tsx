import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerText } from "./AnswerText";

// Real Arabic answer of the API (27/11/2026, shortened): French names and doses inside Arabic text.
const AR =
  "التشخيص: لفحة مبكرة (Alternariose (brûlure alternarienne)) (نسبة الثقة 98 %).\n" +
  "- Score 250 EC (Difenoconazole): الجرعة 0.5 l/ha؛ المدة قبل الجني: 3 أيام\n" +
  "  في المتجر لـScore 250 EC: https://www.agrishop.tn/store/category/Pesticides/Fongicides/score-250-ec/";

describe("AnswerText", () => {
  it("shows the text of the API character for character (only the display is arranged)", () => {
    const { container } = render(<AnswerText text={AR} lang="ar" />);
    expect(container.textContent).toBe(AR);
    const block = container.firstElementChild;
    expect(block).toHaveAttribute("dir", "rtl");
    expect(block).toHaveAttribute("lang", "ar");
    // the French runs are isolated left to right, their brackets stay in place
    const runs = Array.from(container.querySelectorAll("bdi")).map((b) => b.textContent);
    expect(runs).toContain("Alternariose (brûlure alternarienne)");
    expect(runs).toContain("Score 250 EC (Difenoconazole)");
    expect(container.querySelectorAll("bdi[dir=ltr]").length).toBe(runs.length);
    // the link is clickable and left to right
    expect(screen.getByRole("link")).toHaveAttribute("dir", "ltr");
  });

  it("a French answer is left as it is", () => {
    const fr = "Diagnostic : Alternariose (confiance 98 %).\n- Score 250 EC : dose 0.5 l/ha";
    const { container } = render(<AnswerText text={fr} lang="fr" />);
    expect(container.textContent).toBe(fr);
    expect(container.querySelector("bdi")).toBeNull();
  });
});

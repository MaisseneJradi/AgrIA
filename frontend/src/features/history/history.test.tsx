import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { real } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { clearHistory, listHistory, MAX, saveAnswer } from "./history";

beforeEach(async () => {
  await clearHistory();
});

describe("history on the device", () => {
  it("keeps the last 10 answers, newest first, as text (no photo)", async () => {
    for (let i = 0; i < MAX + 2; i++) await saveAnswer(real.conseil_fr, "tomato", new Date(2026, 10, 1 + i));
    const all = await listHistory();
    expect(all).toHaveLength(MAX);
    expect(all[0]?.date).toBe(new Date(2026, 10, 12).toISOString());
    expect(Object.keys(all[0] ?? {})).not.toContain("photo");
    expect(JSON.stringify(all)).not.toMatch(/data:image/);
  });

  it("the page lists them with their date, opens one as an OLD answer, and deletes all", async () => {
    await saveAnswer(real.conseil_fr, "tomato", new Date("2026-11-20T10:00:00"));
    await renderApp("/historique");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Mes dernières réponses" }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Réponse du/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voir" }));
    expect(screen.getByText(/Ancienne réponse, du/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Traitements homologués" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retour à la liste" }));
    await userEvent.click(screen.getByRole("button", { name: "Effacer mon historique" }));
    const buttons = await screen.findAllByRole("button", { name: "Effacer mon historique" });
    await userEvent.click(buttons[buttons.length - 1] as HTMLElement);
    expect(await screen.findByText("Aucune réponse gardée pour l'instant.")).toBeInTheDocument();
    expect(await listHistory()).toEqual([]);
  });
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import ar from "@/locales/ar.json";
import fr from "@/locales/fr.json";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

function keys(o: object, pre = ""): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v as object, `${pre}${k}.`) : [`${pre}${k}`],
  );
}

describe("languages", () => {
  it("French and Arabic have the same texts, none empty", () => {
    expect(keys(ar).sort()).toEqual(keys(fr).sort());
    const empty = (o: object) =>
      keys(o).filter(
        (k) => k.split(".").reduce<unknown>((x, p) => (x as Record<string, unknown>)[p], o) === "",
      );
    expect(empty(fr)).toEqual([]);
    expect(empty(ar)).toEqual([]);
  });
});

describe("pages", () => {
  it("about and limits, in Arabic", async () => {
    await renderApp("/a-propos", "ar");
    expect(await screen.findByRole("heading", { level: 1, name: "حول AgrIA وحدوده" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "اتبع دائمًا الملصق" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "معطياتك" })).toBeInTheDocument();
  });

  it("the footer links to the history and the about page", async () => {
    await renderApp("/");
    const nav = screen.getByRole("navigation", { name: "Menu" });
    expect(within(nav).getByRole("link", { name: "Mes réponses" })).toHaveAttribute("href", "/historique");
    expect(within(nav).getByRole("link", { name: "À propos et limites" })).toHaveAttribute(
      "href",
      "/a-propos",
    );
  });

  it("admin: the token is asked, a wrong one is refused, the journal and the accuracy per crop are shown", async () => {
    const data = {
      analyses: [
        {
          id: "20261127-120000-abcdef",
          date: "2026-11-27T12:00:00",
          culture: "olive",
          gouvernorat: "Sfax",
          langue: "fr",
          issue: "question",
          classe: "olive__peacock_spot",
          maladie: "Œil de paon",
          confiance: 61,
          fiable: false,
          produits: "",
          verdict: "faux",
          vraie_culture: "olive",
          vrai_probleme: "œil de paon",
          vraie_reponse: null,
          commentaire: null,
          garder_photo: true,
          photo: true,
        },
        {
          id: "20261127-110000-abcdef",
          date: "2026-11-27T11:00:00",
          culture: "tomato",
          gouvernorat: "Nabeul",
          langue: "fr",
          issue: "conseil",
          classe: "tomato__early_blight",
          maladie: "Alternariose",
          confiance: 98,
          fiable: true,
          produits: "Score 250 EC",
          verdict: "correct",
          vraie_culture: null,
          vrai_probleme: null,
          vraie_reponse: null,
          commentaire: null,
          garder_photo: false,
          photo: true,
        },
      ],
      par_culture: [
        { culture: "olive", analyses: 1, avec_avis: 1, correct: 0, partiel: 0, faux: 1, precision: 0 },
        { culture: "tomato", analyses: 1, avec_avis: 1, correct: 1, partiel: 0, faux: 0, precision: 1 },
      ],
    };
    server.use(
      http.get("*/admin/journal", ({ request }) =>
        request.headers.get("Authorization") === "Bearer bon"
          ? HttpResponse.json(data)
          : HttpResponse.json({ detail: "jeton" }, { status: 401 }),
      ),
    );
    await renderApp("/admin/test");
    await userEvent.type(await screen.findByLabelText("Jeton d'administration"), "mauvais");
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByText("Jeton refusé.")).toBeInTheDocument();
    const input = screen.getByLabelText("Jeton d'administration");
    await userEvent.clear(input);
    await userEvent.type(input, "bon");
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByRole("region", { name: "Justesse par culture" })).toHaveTextContent("100 %");
    expect(screen.getByRole("region", { name: "Analyses (2)" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Avis"), "faux");
    expect(screen.getByRole("region", { name: "Analyses (1)" })).toHaveTextContent("Œil de paon");
    expect(screen.getByRole("button", { name: "Exporter en CSV" })).toBeInTheDocument();
  });
});

describe("answer cards", () => {
  it("every card type of the API schema has a title in French and in Arabic", async () => {
    const schema = (await import("@/api/openapi.json")).default as unknown as {
      components: { schemas: { Card: { properties: { type: { enum: string[] } } } } };
    };
    for (const type of schema.components.schemas.Card.properties.type.enum) {
      expect((fr.cards as Record<string, unknown>)[type], type).toBeTypeOf("string");
      expect((ar.cards as Record<string, unknown>)[type], type).toBeTypeOf("string");
    }
  });
});

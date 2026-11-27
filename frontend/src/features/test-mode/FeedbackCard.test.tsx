import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useDiagnosis } from "@/features/diagnosis/store";
import { real, TINY_JPEG } from "@/test/fixtures";
import { renderApp, renderWithProviders } from "@/test/render";
import { sentForms, server } from "@/test/server";
import { FeedbackCard } from "./FeedbackCard";

const sent = () => sentForms.filter((s) => s.path === "/feedback").map((s) => s.form);

describe("test mode", () => {
  it("nothing is sent before a verdict is chosen; consent can be given even when the diagnosis is right", async () => {
    server.use(http.post("*/feedback", () => HttpResponse.json({ statut: "enregistré" })));
    await renderWithProviders(<FeedbackCard journalId="20261127-120000-abcdef" />);
    await userEvent.click(screen.getByRole("button", { name: "Envoyer mon avis" }));
    expect(screen.getByText("Choisissez juste, en partie ou faux.")).toBeInTheDocument();
    expect(sent()).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Juste" }));
    await userEvent.click(screen.getByLabelText(/J'accepte qu'AgrIA garde cette photo/));
    await userEvent.click(screen.getByRole("button", { name: "Envoyer mon avis" }));
    expect(await screen.findByText("Merci, votre avis est enregistré.")).toBeInTheDocument();
    const form = sent()[0];
    expect(form?.get("verdict")).toBe("correct");
    expect(form?.get("garder_photo")).toBe("oui");
    expect(form?.get("journal_id")).toBe("20261127-120000-abcdef");
  });

  it("wrong: the true crop (list) and the true problem are sent", async () => {
    server.use(http.post("*/feedback", () => HttpResponse.json({ statut: "enregistré" })));
    await renderWithProviders(<FeedbackCard journalId="20261127-120000-abcdef" />);
    await userEvent.click(screen.getByRole("button", { name: "Faux" }));
    await userEvent.selectOptions(await screen.findByLabelText("La vraie culture"), "olive");
    await userEvent.type(screen.getByLabelText(/Le vrai problème/), "œil de paon");
    await userEvent.click(screen.getByRole("button", { name: "Envoyer mon avis" }));
    await screen.findByText("Merci, votre avis est enregistré.");
    const form = sent()[0];
    expect([form?.get("verdict"), form?.get("vraie_culture"), form?.get("vrai_probleme")]).toEqual([
      "faux",
      "olive",
      "œil de paon",
    ]);
    expect(form?.get("garder_photo")).toBe("non");
  });

  it("banner and opinion only in test mode (journal on the server)", async () => {
    server.use(
      http.get("*/health", () =>
        HttpResponse.json({ statut: "ok", modeles: [], device: "cpu", mode_test: true, admin: false }),
      ),
      http.post("*/diagnose", () =>
        HttpResponse.json({ ...real.conseil_fr, journal_id: "20261127-120000-abcdef" }),
      ),
    );
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "tomato" });
    await renderApp("/reponse");
    expect(await screen.findByText(/Mode test : vos analyses sont enregistrées/)).toBeInTheDocument();
    const card = await screen.findByRole("region", { name: "Votre avis sur ce diagnostic" });
    expect(within(card).getByRole("button", { name: "En partie" })).toBeInTheDocument();
  });
});

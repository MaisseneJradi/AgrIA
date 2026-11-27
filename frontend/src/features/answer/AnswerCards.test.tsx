import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerView } from "@/features/diagnosis/AnswerStep";
import { diagnoseUnreliable, real } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { expectLogicalDirectionOnly } from "@/test/utils";
import { isReliable, visibleCards } from "./cards";

const conseil = real.conseil_fr;

describe("answer cards (real answer of the API)", () => {
  it("every card of the API is shown, in the order diagnosis -> treatments -> water -> advice", async () => {
    const { container } = await renderWithProviders(
      <AnswerView answer={conseil} cropLabel="Tomate" pageLang="fr" />,
    );
    const titles = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titles.slice(0, 3)).toEqual(["Diagnostic", "Traitements homologués", "Sécurité"]);
    expect(titles).toContain("Irrigation");
    // the confidence in words, never the probability alone
    expect(
      within(screen.getByRole("region", { name: "Diagnostic" })).getAllByText("Sûr").length,
    ).toBeGreaterThan(0);
    // every line of the API is on the screen, unchanged
    for (const card of conseil.cartes.filter((c) => c.type !== "affiner")) {
      for (const piece of card.elements ?? card.citations ?? [card.texte]) {
        if (!card.produits) expect(container.textContent).toContain(piece.split("https://")[0]?.trim());
      }
    }
    expectLogicalDirectionOnly(container);
  });

  it("one card per product with its lines; a shop button only where the API gives a validated link", async () => {
    await renderWithProviders(<AnswerView answer={conseil} cropLabel="Tomate" pageLang="fr" />);
    const products = screen.getAllByRole("article");
    expect(products).toHaveLength(3);
    const [score, cuproxat] = products;
    if (!score || !cuproxat) throw new Error("products");
    expect(within(score).getByText(/dose 0\.5 l\/ha ; délai avant récolte : 3 jours/)).toBeInTheDocument();
    expect(within(score).getByText(/Dose pratique/)).toBeInTheDocument();
    const shop = within(score).getByRole("link", { name: "Voir la page du produit" });
    expect(shop).toHaveAttribute(
      "href",
      "https://www.agrishop.tn/store/category/Pesticides/Fongicides/score-250-ec/",
    );
    // no validated shop product: the "ask for" sentence, no shop button
    expect(within(cuproxat).getByText(/non trouvé sur agrishop\.tn/)).toBeInTheDocument();
    expect(within(cuproxat).queryByRole("link", { name: "Voir la page du produit" })).not.toBeInTheDocument();
  });

  it("an Arabic answer: right to left, product names isolated left to right", async () => {
    const { container } = await renderWithProviders(
      <AnswerView answer={real.conseil_ar} cropLabel="طماطم" pageLang="ar" />,
      "ar",
    );
    expect(screen.getAllByRole("heading", { level: 2 })[0]).toHaveTextContent("التشخيص");
    expect(container.querySelector('[lang="ar"][dir="rtl"]')).not.toBeNull();
    expect(
      Array.from(container.querySelectorAll("bdi")).some((b) => b.textContent?.includes("Score 250 EC")),
    ).toBe(true);
  });

  it("rule 3: not reliable -> only the doubt and the questions, never a product or a treatment card", async () => {
    expect(isReliable(diagnoseUnreliable)).toBe(false);
    expect(visibleCards(diagnoseUnreliable).map((c) => c.type)).toEqual(["doute", "pistes", "questions"]);
    await renderWithProviders(<AnswerView answer={diagnoseUnreliable} cropLabel="Olivier" pageLang="fr" />);
    expect(screen.getByText(/aucun produit n'est conseillé avant confirmation/)).toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.queryByText(/Score 250 EC|Cuproxat|l\/ha/)).not.toBeInTheDocument();
    expect(screen.getAllByText("Pas sûr").length).toBeGreaterThan(0);
  });

  it("how AgrIA decided: the steps of the agents, folded", async () => {
    await renderWithProviders(<AnswerView answer={conseil} cropLabel="Tomate" pageLang="fr" />);
    const details = screen.getByText("Comment AgrIA a décidé").closest("details");
    expect(details).not.toHaveAttribute("open");
    expect(within(details as HTMLElement).getAllByRole("listitem")).toHaveLength(conseil.trace.length);
    expect(within(details as HTMLElement).getByText("Vérificateur")).toBeInTheDocument();
  });
});

import { screen } from "@testing-library/react";
import { SprayCan } from "lucide-react";
import { describe, expect, it } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { Card } from "./Card";

describe.each(["fr", "ar"] as const)("Card (%s)", (lang) => {
  it("is a region named by its title, with the heading level asked", async () => {
    const { container } = await renderIn(
      lang,
      <Card title="Traitements" icon={SprayCan} level={3} tone="warning">
        <p>contenu</p>
      </Card>,
    );
    const region = screen.getByRole("region", { name: "Traitements" });
    expect(region).toHaveTextContent("contenu");
    expect(screen.getByRole("heading", { level: 3, name: "Traitements" })).toBeInTheDocument();
    // the coloured edge is on the start side (left in French, right in Arabic)
    expect(region.className).toMatch(/border-s-4/);
    expectLogicalDirectionOnly(container);
  });

  it("without a title it is a plain block", async () => {
    await renderIn(lang, <Card>texte</Card>);
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(screen.getByText("texte")).toBeInTheDocument();
  });
});

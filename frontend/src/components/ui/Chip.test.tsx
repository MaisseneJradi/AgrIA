import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Leaf } from "lucide-react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { Chip } from "./Chip";

function Choice() {
  const [v, setV] = useState("a");
  return (
    <>
      <Chip icon={Leaf} selected={v === "a"} onSelectedChange={() => setV("a")}>
        Tomate
      </Chip>
      <Chip icon={Leaf} selected={v === "b"} onSelectedChange={() => setV("b")}>
        Olivier
      </Chip>
    </>
  );
}

describe.each(["fr", "ar"] as const)("Chip (%s)", (lang) => {
  it("tells its state with aria-pressed and switches on tap", async () => {
    const { container } = await renderIn(lang, <Choice />);
    const tomato = screen.getByRole("button", { name: "Tomate" });
    const olive = screen.getByRole("button", { name: "Olivier" });
    expect(tomato).toHaveAttribute("aria-pressed", "true");
    expect(olive).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(olive);
    expect(olive).toHaveAttribute("aria-pressed", "true");
    expect(tomato).toHaveAttribute("aria-pressed", "false");
    expect(olive.className).toMatch(/min-h-touch/);
    expectLogicalDirectionOnly(container);
  });
});

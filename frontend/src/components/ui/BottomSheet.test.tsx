import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { BottomSheet } from "./BottomSheet";

function Demo() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        ouvrir
      </button>
      <BottomSheet open={open} onOpenChange={setOpen} title="Autre culture">
        <button type="button">Tomate</button>
      </BottomSheet>
    </>
  );
}

describe.each(["fr", "ar"] as const)("BottomSheet (%s)", (lang) => {
  it("opens as a named dialog, closes with its button and with Escape, focus goes back", async () => {
    await renderIn(lang, <Demo />);
    const opener = screen.getByRole("button", { name: "ouvrir" });
    await userEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "Autre culture" });
    expect(dialog).toBeInTheDocument();
    expectLogicalDirectionOnly(dialog);
    await userEvent.click(screen.getByRole("button", { name: lang === "fr" ? "Fermer" : "إغلاق" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(opener).toHaveFocus()); // focus back on the button that opened it
    await userEvent.click(opener);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

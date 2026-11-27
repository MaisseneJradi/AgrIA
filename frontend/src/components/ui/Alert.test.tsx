import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { Alert } from "./Alert";

describe.each(["fr", "ar"] as const)("Alert (%s)", (lang) => {
  it("errors and warnings are announced at once, information politely", async () => {
    const { container } = await renderIn(
      lang,
      <>
        <Alert tone="danger" title="Pas de connexion" />
        <Alert tone="info" title="Bon à savoir" />
      </>,
    );
    const box = within(container); // (the toast region of the page is a status too)
    expect(box.getByRole("alert")).toHaveTextContent("Pas de connexion");
    expect(box.getByRole("status")).toHaveTextContent("Bon à savoir");
    expectLogicalDirectionOnly(container);
  });

  it("has a dismiss button named in the language of the page, and an action", async () => {
    const onDismiss = vi.fn();
    await renderIn(
      lang,
      <Alert tone="warning" onDismiss={onDismiss} action={<button type="button">retry</button>}>
        texte
      </Alert>,
    );
    const close = screen.getByRole("button", {
      name: lang === "fr" ? "Masquer le message" : "إخفاء الرسالة",
    });
    await userEvent.click(close);
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "retry" })).toBeInTheDocument();
  });
});

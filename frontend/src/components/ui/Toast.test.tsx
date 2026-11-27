import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { TOAST_MS, useToast } from "./toast-context";

function Demo() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.show("Copié", "success")}>
      montrer
    </button>
  );
}

afterEach(() => vi.useRealTimers());

describe.each(["fr", "ar"] as const)("Toast (%s)", (lang) => {
  it("is read by screen readers and goes away by itself", async () => {
    const { container } = await renderIn(lang, <Demo />, { withToast: true });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await userEvent.click(screen.getByRole("button", { name: "montrer" }));
    const live = screen.getByRole("status");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveTextContent("Copié");
    expectLogicalDirectionOnly(container);
    act(() => {
      vi.advanceTimersByTime(TOAST_MS + 10);
    });
    expect(live).not.toHaveTextContent("Copié");
  });

  it("can be closed by its button", async () => {
    await renderIn(lang, <Demo />, { withToast: true });
    await userEvent.click(screen.getByRole("button", { name: "montrer" }));
    await userEvent.click(
      screen.getByRole("button", { name: lang === "fr" ? "Masquer le message" : "إخفاء الرسالة" }),
    );
    expect(screen.getByRole("status")).not.toHaveTextContent("Copié");
  });
});

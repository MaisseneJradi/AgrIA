import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { real } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";
import { AnswerActions } from "./AnswerExtras";

const answer = real.conseil_fr;

afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "share");
});

describe("answer actions", () => {
  it("share: the text of the API, by the share sheet of the phone", async () => {
    const share = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "share", { value: share, configurable: true });
    await renderWithProviders(<AnswerActions answer={answer} />);
    await userEvent.click(screen.getByRole("button", { name: "Partager" }));
    expect(share).toHaveBeenCalledWith({ title: "Réponse d'AgrIA", text: answer.texte });
  });

  it("without a share sheet: copied, and said", async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await renderWithProviders(<AnswerActions answer={answer} />);
    await userEvent.click(screen.getByRole("button", { name: "Partager" }));
    expect(writeText).toHaveBeenCalledWith(answer.texte);
    expect(await screen.findByText(/Réponse copiée/)).toBeInTheDocument();
  });

  it("read aloud only when the phone can speak, in the language of the answer", async () => {
    await renderWithProviders(<AnswerActions answer={answer} />);
    expect(screen.queryByRole("button", { name: "Lire à voix haute" })).not.toBeInTheDocument();
  });

  it("read aloud speaks the text of the API", async () => {
    const speak = vi.fn();
    vi.stubGlobal("speechSynthesis", { speak, cancel: vi.fn() });
    vi.stubGlobal(
      "SpeechSynthesisUtterance",
      class {
        lang = "";
        onend: (() => void) | null = null;
        onerror: (() => void) | null = null;
        constructor(public text: string) {}
      },
    );
    await renderWithProviders(<AnswerActions answer={real.conseil_ar} />);
    await userEvent.click(screen.getByRole("button", { name: "Lire à voix haute" }));
    const u = speak.mock.calls[0]?.[0] as { text: string; lang: string };
    expect(u.text).toBe(real.conseil_ar.texte);
    expect(u.lang).toBe("ar");
    expect(screen.getByRole("button", { name: "Arrêter la lecture" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("print", async () => {
    const print = vi.fn();
    vi.stubGlobal("print", print);
    await renderWithProviders(<AnswerActions answer={answer} />);
    await userEvent.click(screen.getByRole("button", { name: "Imprimer ou PDF" }));
    expect(print).toHaveBeenCalled();
  });
});

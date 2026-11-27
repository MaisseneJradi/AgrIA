import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { routes } from "@/app/routes";
import { setLang } from "@/lib/i18n";
import { TINY_JPEG } from "@/test/fixtures";
import { useDiagnosis } from "./store";

const initial = useDiagnosis.getState();

async function renderContext() {
  await act(async () => {
    await setLang("fr");
  });
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/precisions"] })} />
    </QueryClientProvider>,
  );
}

class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = "";
  interimResults = false;
  continuous = false;
  onresult: ((e: { results: Array<Array<{ transcript: string }>> }) => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  start() {
    FakeRecognition.last = this;
  }
  stop() {
    this.onend?.();
  }
}

beforeEach(() => {
  useDiagnosis.setState(
    { ...initial, photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "tomato" },
    true,
  );
});
afterEach(() => {
  delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
});

describe("context step", () => {
  it("no dictation button when the browser cannot listen", async () => {
    await renderContext();
    expect(await screen.findByLabelText("Décrivez le problème")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dicter" })).not.toBeInTheDocument();
  });

  it("dictation puts the sentence in the message, in the language of the page", async () => {
    (window as unknown as Record<string, unknown>).webkitSpeechRecognition = FakeRecognition;
    await renderContext();
    await userEvent.type(await screen.findByLabelText("Décrivez le problème"), "tomates");
    await userEvent.click(screen.getByRole("button", { name: "Dicter" }));
    expect(screen.getByText("Je vous écoute…")).toBeInTheDocument();
    const rec = FakeRecognition.last;
    expect(rec?.lang).toBe("fr-FR");
    act(() => {
      rec?.onresult?.({ results: [[{ transcript: "taches noires" }]] });
      rec?.onend?.();
    });
    expect(screen.getByLabelText("Décrivez le problème")).toHaveValue("tomates taches noires");
  });

  it("a chip tapped twice is unselected (the field is then not sent)", async () => {
    await renderContext();
    const yes = (await screen.findAllByRole("button", { name: "Oui" }))[0];
    if (!yes) throw new Error("no chip");
    await userEvent.click(yes);
    expect(useDiagnosis.getState().context.organic).toBe("oui");
    await userEvent.click(yes);
    expect(useDiagnosis.getState().context).not.toHaveProperty("organic");
  });
});

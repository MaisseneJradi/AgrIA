import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DiagnoseAnswer } from "@/api/client";
import { routes } from "@/app/routes";
import { ToastProvider } from "@/components/ui";
import { setLang, type Lang } from "@/lib/i18n";
import {
  diagnoseArabic,
  diagnoseConseil,
  diagnoseUnreliable,
  identifyNotPlant,
  identifySure,
  identifyUnsure,
  TINY_JPEG,
} from "@/test/fixtures";
import { sentForms, server } from "@/test/server";
import { GOV_KEY, useDiagnosis } from "./store";

// the canvas of jsdom cannot decode images: the preparation of the photo is replaced (tested in lib/image.test.ts)
vi.mock("@/lib/image", async (orig) => ({
  ...(await orig<typeof import("@/lib/image")>()),
  preparePhoto: vi.fn(async () => ({ dataUrl: TINY_JPEG, width: 800, height: 600, bytes: 60 })),
}));

const initial = useDiagnosis.getState();
/** the forms sent to a route, in order (recorded by src/test/setup.ts) */
const sent = (route: string) => sentForms.filter((s) => s.path === `/${route}`).map((s) => s.form);

/** the mocked API: an answer of /diagnose, or a function that builds the HTTP response (errors) */
function useApi(identify = identifySure, diagnose: DiagnoseAnswer | (() => Response) = diagnoseConseil) {
  server.use(
    http.post("*/identify", () => HttpResponse.json(identify)),
    http.post("*/diagnose", () =>
      typeof diagnose === "function" ? diagnose() : HttpResponse.json(diagnose),
    ),
  );
}

async function renderApp(path: string, lang: Lang = "fr") {
  await act(async () => {
    await setLang(lang);
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

function choosePhoto() {
  const file = new File(["x"], "feuille.jpg", { type: "image/jpeg" });
  fireEvent.change(screen.getByTestId("camera-input"), { target: { files: [file] } });
}

beforeEach(() => {
  useDiagnosis.setState(initial, true);
});
afterEach(() => sessionStorage.clear());

describe("farmer flow", () => {
  it("photo -> crop confirmed -> context -> answer, the form sent is what the farmer entered", async () => {
    useApi();
    const router = await renderApp("/");
    expect(screen.getByRole("heading", { level: 1, name: "Prenez une photo de la plante" })).toHaveFocus();
    choosePhoto();
    expect(await screen.findByAltText("Votre photo")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continuer" }));

    // crop: the 3 proposals of /identify as buttons, the sure one marked, nothing chosen for the farmer
    const tomato = await screen.findByRole("button", { name: /Tomate/ });
    expect(within(tomato).getByText("proposé")).toBeInTheDocument();
    expect(tomato).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Pommier" })).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument(); // never a raw probability
    expect(screen.queryByText(/Autre plante/)).not.toBeInTheDocument(); // not a crop of /cultures
    const next = screen.getByRole("button", { name: "Continuer" });
    expect(next).toBeDisabled(); // the farmer must confirm
    await userEvent.click(tomato);
    expect(next).toBeEnabled();
    await userEvent.click(next);

    // context: governorate from the list (kept on the device), the market as a tap
    await userEvent.click(await screen.findByRole("button", { name: /Choisir le gouvernorat/ }));
    const dialog = await screen.findByRole("dialog", { name: "Gouvernorat" });
    await userEvent.type(within(dialog).getByRole("searchbox"), "sfa");
    await userEvent.click(within(dialog).getByRole("button", { name: "Sfax" }));
    expect(localStorage.getItem(GOV_KEY)).toBe("Sfax");
    await userEvent.click(screen.getByRole("button", { name: "Export (Union européenne)" }));
    await userEvent.type(screen.getByLabelText("Décrivez le problème"), "taches noires");
    await userEvent.click(screen.getByRole("button", { name: "Analyser la photo" }));

    // answer: the text of the API as is, links clickable
    expect(
      await screen.findByText(/Diagnostic : Alternariose \(brûlure alternarienne\)/),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/reponse");
    const link = screen.getByRole("link", { name: /agrishop\.tn/ });
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    const form = sent("diagnose")[0];
    expect(form?.get("culture")).toBe("tomato");
    expect(form?.get("langue")).toBe("fr");
    expect(form?.get("gouvernorat")).toBe("Sfax");
    expect(form?.get("market")).toBe("export");
    expect(form?.get("message")).toBe("taches noires");
    expect(form?.get("mois")).toBe(String(new Date().getMonth() + 1));
    expect(form?.get("photo")).toBeInstanceOf(File);
    expect(form?.get("days_to_harvest")).toBeNull(); // empty: not sent
    // the answer as cards: diagnosis with the confidence in words, the products, safety
    expect(screen.getByRole("region", { name: "Diagnostic" })).toHaveTextContent("Sûr");
    expect(screen.getByRole("region", { name: "Traitements homologués" })).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.getByRole("region", { name: "Sécurité" })).toBeInTheDocument();
    expect(sent("diagnose")).toHaveLength(1);
    expect(sent("identify")[0]?.get("photo")).toBeInstanceOf(File);
  });

  it("in Arabic the crops come with their Arabic names; an unsure crop is not marked", async () => {
    useApi(identifyUnsure);
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 } });
    await renderApp("/culture", "ar");
    expect(await screen.findByRole("button", { name: "زيتون" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "طماطم" })).toBeInTheDocument();
    expect(screen.queryByText("مقترح")).not.toBeInTheDocument();
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("a photo that is not a plant: said clearly, with a button to take another one", async () => {
    useApi(identifyNotPlant);
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 } });
    const router = await renderApp("/culture");
    expect(await screen.findByText("Ce n'est pas une plante")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reprendre une photo" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("another crop from the searchable list", async () => {
    useApi();
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 } });
    await renderApp("/culture");
    await userEvent.click(await screen.findByRole("button", { name: "Autre culture" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByRole("searchbox"), "oliv");
    expect(within(dialog).queryByRole("button", { name: "Tomate" })).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Olivier" }));
    expect(useDiagnosis.getState().crop).toBe("olive");
    expect(screen.getByText("Culture choisie : Olivier")).toBeInTheDocument();
  });

  it("no network on the analysis: a clear message and retry, which works", async () => {
    let fail = true;
    useApi(identifySure, () => (fail ? HttpResponse.error() : HttpResponse.json(diagnoseConseil)));
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "tomato" });
    await renderApp("/reponse");
    expect(await screen.findByText(/Vérifiez votre connexion/)).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByText(/Diagnostic : Alternariose/)).toBeInTheDocument();
  });

  it("server error and unreadable photo have their own message", async () => {
    useApi(identifySure, () => HttpResponse.json({ detail: "boom" }, { status: 500 }));
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "tomato" });
    await renderApp("/reponse");
    expect(await screen.findByText("Le serveur a rencontré une erreur. Réessayez.")).toBeInTheDocument();
    server.use(http.post("*/diagnose", () => HttpResponse.json({ detail: "x" }, { status: 415 })));
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByText(/La photo n'a pas pu être lue/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reprendre une photo" })).toBeInTheDocument();
  });

  it("rule 3: diagnosis not reliable -> only the questions, never a product, even if the API sent one", async () => {
    useApi(identifySure, diagnoseUnreliable);
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "tomato" });
    await renderApp("/reponse");
    expect(await screen.findByText(/Je ne suis pas encore sûr/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Diagnostic incertain" })).toBeInTheDocument();
    expect(screen.getByText(/aucun produit n'est conseillé avant confirmation/)).toBeInTheDocument();
    expect(screen.queryByText(/Score 250 EC/)).not.toBeInTheDocument();
    expect(screen.queryByText(/0\.5 l\/ha/)).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Traitements homologués" })).not.toBeInTheDocument();
  });

  it("the questions of the agents are answered on the answer screen, then sent again", async () => {
    useApi();
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "tomato" });
    await renderApp("/reponse");
    const refine = await screen.findByRole("region", { name: "Répondez pour affiner" });
    // only the fields the API asked for
    expect(within(refine).getByText("Pour quel marché ?")).toBeInTheDocument();
    expect(within(refine).queryByText("Sous serre ?")).not.toBeInTheDocument();
    await userEvent.click(within(refine).getByRole("button", { name: "14 jours" }));
    await userEvent.click(
      within(refine).getByRole("button", { name: "Relancer l'analyse avec ces réponses" }),
    );
    await waitFor(() => expect(sent("diagnose")).toHaveLength(2));
    expect(sent("diagnose")[1]?.get("days_to_harvest")).toBe("14");
  });

  it("an answer in the other language says so and can be asked again in the language of the page", async () => {
    useApi(identifySure, diagnoseArabic);
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "tomato" });
    await renderApp("/reponse");
    const text = await screen.findByText(/التشخيص/);
    expect(text.closest("[dir]")).toHaveAttribute("dir", "rtl");
    expect(screen.getByText("Cette réponse est en arabe.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Afficher la réponse en français" }));
    await waitFor(() => expect(sent("diagnose")).toHaveLength(2));
  });

  it("a step opened without what it needs goes back to the first missing step", async () => {
    let router = await renderApp("/reponse");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 } });
    useApi();
    router = await renderApp("/precisions");
    await waitFor(() => expect(router.state.location.pathname).toBe("/culture"));
  });

  it("a reload keeps the photo, the crop and the context, never the answer", async () => {
    useDiagnosis.setState({ photo: { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 }, crop: "olive" });
    useDiagnosis.getState().setContext({ market: "local" });
    useDiagnosis.getState().setAnswer(diagnoseConseil);
    const kept = JSON.parse(sessionStorage.getItem("agria-diagnostic") ?? "{}").state;
    expect(kept.crop).toBe("olive");
    expect(kept.photo.dataUrl).toBe(TINY_JPEG);
    expect(kept.context).toEqual({ market: "local" });
    expect(kept.answer).toBeUndefined();
    // a new photo forgets what depended on the old one
    useDiagnosis.getState().setPhoto({ dataUrl: TINY_JPEG, width: 1, height: 1, bytes: 1 });
    expect(useDiagnosis.getState().crop).toBeNull();
  });
});

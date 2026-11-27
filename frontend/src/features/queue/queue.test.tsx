import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useDiagnosis } from "@/features/diagnosis/store";
import { real, TINY_JPEG } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { sentForms, server } from "@/test/server";
import { clearPending, getPending, setPending } from "./queue";

const initial = useDiagnosis.getState();
const photo = { dataUrl: TINY_JPEG, width: 8, height: 8, bytes: 60 };

beforeEach(async () => {
  useDiagnosis.setState(initial, true);
  await clearPending();
});

describe("one photo waiting for the network", () => {
  it("no network: the farmer can put the photo aside, and cancel", async () => {
    server.use(http.post("*/diagnose", () => HttpResponse.error()));
    useDiagnosis.setState({ photo, crop: "tomato", context: { market: "local" } });
    await renderApp("/reponse");
    await userEvent.click(await screen.findByRole("button", { name: "Envoyer quand le réseau revient" }));
    expect(await screen.findByText(/Photo en attente depuis le/)).toBeInTheDocument();
    const p = await getPending();
    expect(p?.crop).toBe("tomato");
    expect(p?.context).toEqual({ market: "local" });
    await userEvent.click(screen.getByRole("button", { name: "Annuler l'envoi" }));
    await waitFor(async () => expect(await getPending()).toBeNull());
  });

  it("network back: the analysis is asked, the answer says when the photo was put aside", async () => {
    server.use(http.post("*/diagnose", () => HttpResponse.json(real.conseil_fr)));
    await setPending({
      date: "2026-11-20T08:00:00.000Z",
      photo,
      crop: "olive",
      message: "taches",
      gouvernorat: "Sfax",
      context: {},
      langue: "fr",
    });
    const router = await renderApp("/");
    await waitFor(() => expect(router.state.location.pathname).toBe("/reponse"));
    expect(await screen.findByText(/Votre photo mise en attente le/)).toBeInTheDocument();
    const form = sentForms.filter((s) => s.path === "/diagnose")[0]?.form;
    expect(form?.get("culture")).toBe("olive");
    expect(form?.get("gouvernorat")).toBe("Sfax");
    expect(await getPending()).toBeNull();
  });
});

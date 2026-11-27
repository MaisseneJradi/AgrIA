// Mocked API (MSW) for the unit and component tests. The bodies are typed with the generated API types: when the
// backend schema changes, the fixtures stop compiling.
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { Gouvernorat, Health } from "@/api/client";
import { real } from "./fixtures";

export const fixtures = {
  health: {
    statut: "ok",
    modeles: ["crop", "diseases"],
    device: "cpu",
    mode_test: false,
    admin: false,
  } satisfies Health,
  cultures: real.cultures, // the 14 crops of the API
  gouvernorats: [
    { fr: "Nabeul", ar: "نابل" },
    { fr: "Sfax", ar: "صفاقس" },
  ] satisfies Gouvernorat[],
};

export const handlers = [
  http.get("*/health", () => HttpResponse.json(fixtures.health)),
  http.get("*/cultures", () => HttpResponse.json(fixtures.cultures)),
  http.get("*/gouvernorats", () => HttpResponse.json(fixtures.gouvernorats)),
];

export const server = setupServer(...handlers);

/** The forms the app sent (path of the route, FormData), in order: see src/test/setup.ts. */
export const sentForms: Array<{ path: string; form: FormData }> = [];

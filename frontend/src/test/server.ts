// Mocked API (MSW) for the unit and component tests. The bodies are typed with the generated API types: when the
// backend schema changes, the fixtures stop compiling.
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { Culture, Gouvernorat, Health } from "@/api/client";

export const fixtures = {
  health: { statut: "ok", modeles: ["crop", "diseases"], device: "cpu" } satisfies Health,
  cultures: [
    { code: "tomato", fr: "Tomate", ar: "طماطم" },
    { code: "olive", fr: "Olivier", ar: "زيتون" },
  ] satisfies Culture[],
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

import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fixtures, server } from "@/test/server";
import { api, ApiError, NetworkError } from "./client";

describe("API client", () => {
  it("returns the typed lists", async () => {
    expect(await api.cultures()).toEqual(fixtures.cultures);
    expect((await api.gouvernorats())[1]).toEqual({ fr: "Sfax", ar: "صفاقس" });
  });

  it("an error keeps the HTTP status and the message of FastAPI", async () => {
    server.use(
      http.post("*/identify", () => HttpResponse.json({ detail: "format accepté : JPEG" }, { status: 415 })),
    );
    const err = await api.identify(new Blob(["x"])).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 415, detail: "format accepté : JPEG" });
  });

  it("no answer at all is a network error", async () => {
    server.use(http.get("*/health", () => HttpResponse.error()));
    await expect(api.health()).rejects.toBeInstanceOf(NetworkError);
  });
});

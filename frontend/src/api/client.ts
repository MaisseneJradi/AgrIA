// Calls to the AgrIA API. The types come from the OpenAPI schema of FastAPI (src/api/schemas.py ->
// openapi.json -> schema.d.ts, `npm run api:schema && npm run api:types`): frontend and backend stay in sync.
// The app displays what the API returns; it never computes a dose, a level or a product.
import type { components } from "./schema";

type S = components["schemas"];
export type Health = S["Health"];
export type Gouvernorat = S["Gouvernorat"];
export type Culture = S["Culture"];
export type IdentifyAnswer = S["Identify"];
export type DiagnoseAnswer = S["Diagnose"];
export type FeedbackSaved = S["FeedbackSaved"];

/** An answer of the API other than 2xx: its HTTP status and the message of FastAPI ("detail"), if any. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string | null,
  ) {
    super(detail ?? `HTTP ${status}`);
    this.name = "ApiError";
  }
}

/** No answer at all (no network, server stopped). */
export class NetworkError extends Error {
  constructor() {
    super("network");
    this.name = "NetworkError";
  }
}

/** The server did not answer in time (weak network, models busy): treated like a network error, with its own text. */
export class TimeoutError extends Error {
  constructor() {
    super("timeout");
    this.name = "TimeoutError";
  }
}

// one analysis at a time on the server (4 GB GPU) and the VLM: a diagnosis can take a minute on a busy server
export const TIMEOUT_MS = { lists: 20_000, identify: 60_000, diagnose: 120_000 };

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = TIMEOUT_MS.lists): Promise<T> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(path, { ...init, signal: abort.signal });
  } catch {
    throw abort.signal.aborted ? new TimeoutError() : new NetworkError();
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail: string | null = null;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/health"),
  gouvernorats: () => request<Gouvernorat[]>("/gouvernorats"),
  cultures: () => request<Culture[]>("/cultures"),
  identify: (photo: Blob) => {
    const form = new FormData();
    form.append("photo", photo, "photo.jpg");
    return request<IdentifyAnswer>("/identify", { method: "POST", body: form }, TIMEOUT_MS.identify);
  },
  diagnose: (form: FormData) =>
    request<DiagnoseAnswer>("/diagnose", { method: "POST", body: form }, TIMEOUT_MS.diagnose),
  feedback: (form: FormData) => request<FeedbackSaved>("/feedback", { method: "POST", body: form }),
};

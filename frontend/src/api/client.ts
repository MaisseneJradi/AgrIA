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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new NetworkError();
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
    return request<IdentifyAnswer>("/identify", { method: "POST", body: form });
  },
  diagnose: (form: FormData) => request<DiagnoseAnswer>("/diagnose", { method: "POST", body: form }),
  feedback: (form: FormData) => request<FeedbackSaved>("/feedback", { method: "POST", body: form }),
};

import type { TFunction } from "i18next";
import { ApiError, NetworkError, TimeoutError } from "@/api/client";
import { PhotoError } from "@/lib/image";

export type ErrorKind = "network" | "timeout" | "server" | "photo" | "invalid";

/** The message shown for an error, in the language of the page, and what the farmer can do about it. */
export function describeError(err: unknown, t: TFunction): { kind: ErrorKind; text: string } {
  if (err instanceof TimeoutError) return { kind: "timeout", text: t("error.timeout") };
  if (err instanceof NetworkError) return { kind: "network", text: t("error.network") };
  if (err instanceof PhotoError)
    return { kind: "photo", text: t(err.kind === "notImage" ? "photo.errNotImage" : "photo.errUnsupported") };
  if (err instanceof ApiError) {
    if (err.status === 413) return { kind: "photo", text: t("error.photoTooBig") };
    if (err.status === 415) return { kind: "photo", text: t("error.photoUnreadable") };
    if (err.status >= 400 && err.status < 500)
      return { kind: "invalid", text: t("error.invalid", { detail: err.detail ?? "" }) };
  }
  return { kind: "server", text: t("error.server") };
}

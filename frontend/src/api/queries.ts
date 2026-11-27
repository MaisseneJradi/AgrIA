import { QueryClient, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "./client";

/** Retries: a lost network or a 5xx is retried twice; a 4xx (bad photo, bad input) never. */
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false }, // a diagnosis is sent again only when the farmer taps "retry"
    },
  });
}

/** The lists change only with a new version of AgrIA: loaded once. */
export const useCultures = () =>
  useQuery({ queryKey: ["cultures"], queryFn: api.cultures, staleTime: Infinity });
export const useGouvernorats = () =>
  useQuery({ queryKey: ["gouvernorats"], queryFn: api.gouvernorats, staleTime: Infinity });

/** Test mode (journal on the server) and admin: asked once; on failure the app is simply not in test mode. */
export const useHealth = () =>
  useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 5 * 60_000, retry: false });

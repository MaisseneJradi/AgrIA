import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "@/app/routes";
import { ToastProvider } from "@/components/ui";
import { setLang, type Lang } from "@/lib/i18n";

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

/** The whole app at an address, in a language (routes of src/app/routes.tsx, mocked API of src/test/server.ts). */
export async function renderApp(path: string, lang: Lang = "fr") {
  await act(async () => {
    await setLang(lang);
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client()}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

/** One component with the providers it may need (queries, toasts, router links). */
export async function renderWithProviders(ui: ReactElement, lang: Lang = "fr") {
  await act(async () => {
    await setLang(lang);
  });
  return render(
    <QueryClientProvider client={client()}>
      <ToastProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

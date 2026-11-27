import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { makeQueryClient } from "@/api/queries";
import { ToastProvider } from "@/components/ui";
import { routes } from "./routes";

export function App() {
  const [client] = useState(makeQueryClient);
  const [router] = useState(() =>
    createBrowserRouter(routes, {
      future: {
        v7_relativeSplatPath: true,
        v7_fetcherPersist: true,
        v7_normalizeFormMethod: true,
        v7_partialHydration: true,
        v7_skipActionErrorRevalidation: true,
      },
    }),
  );
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} future={{ v7_startTransition: true }} />
      </ToastProvider>
    </QueryClientProvider>
  );
}

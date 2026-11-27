import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router-dom";
import { makeQueryClient } from "@/api/queries";
import { SkeletonBlock, ToastProvider } from "@/components/ui";
import { Home } from "@/pages/Home";
import { Layout } from "./Layout";

// The style guide exists only in development: the condition is false in a production build, so Vite leaves the page
// (and its code) out of dist.
const Styleguide = import.meta.env.DEV ? lazy(() => import("@/pages/Styleguide")) : null;

const children: RouteObject[] = [{ index: true, element: <Home /> }];
if (Styleguide) {
  children.push({
    path: "styleguide",
    element: (
      <Suspense fallback={<SkeletonBlock lines={6} />}>
        <Styleguide />
      </Suspense>
    ),
  });
}

const routes: RouteObject[] = [{ path: "/", element: <Layout />, children }];

export function App() {
  const [client] = useState(makeQueryClient);
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  );
}

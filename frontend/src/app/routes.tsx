import { lazy, Suspense } from "react";
import type { RouteObject } from "react-router-dom";
import { SkeletonBlock } from "@/components/ui";
import { AnswerStep } from "@/features/diagnosis/AnswerStep";
import { ContextStep } from "@/features/diagnosis/ContextStep";
import { CropStep } from "@/features/diagnosis/CropStep";
import { PhotoStep } from "@/features/diagnosis/PhotoStep";
import { RequireFlow } from "@/features/diagnosis/RequireFlow";
import { Layout } from "./Layout";

// The style guide exists only in development: the condition is false in a production build, so Vite leaves the page
// (and its code) out of dist.
const Styleguide = import.meta.env.DEV ? lazy(() => import("@/pages/Styleguide")) : null;

// the farmer flow, one address per step: the phone's back button goes to the previous step
const children: RouteObject[] = [
  { index: true, element: <PhotoStep /> },
  {
    path: "culture",
    element: (
      <RequireFlow need="photo">
        <CropStep />
      </RequireFlow>
    ),
  },
  {
    path: "precisions",
    element: (
      <RequireFlow need="crop">
        <ContextStep />
      </RequireFlow>
    ),
  },
  {
    path: "reponse",
    element: (
      <RequireFlow need="crop">
        <AnswerStep />
      </RequireFlow>
    ),
  },
];
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

export const routes: RouteObject[] = [{ path: "/", element: <Layout />, children }];

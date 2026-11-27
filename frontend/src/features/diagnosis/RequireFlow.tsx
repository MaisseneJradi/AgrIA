import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { STEP_PATH } from "./steps";
import { useDiagnosis } from "./store";

/** A step opened without what it needs (link, back button after a new diagnosis) goes back to the first missing
 * step: no crop without a photo, no answer without a confirmed crop. */
export function RequireFlow({ need, children }: { need: "photo" | "crop"; children: ReactNode }) {
  const photo = useDiagnosis((s) => s.photo);
  const crop = useDiagnosis((s) => s.crop);
  if (!photo) return <Navigate to={STEP_PATH.photo} replace />;
  if (need === "crop" && !crop) return <Navigate to={STEP_PATH.crop} replace />;
  return <>{children}</>;
}

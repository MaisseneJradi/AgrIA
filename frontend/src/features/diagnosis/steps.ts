/** The four steps of the farmer flow and their addresses. */
export const STEP_IDS = ["photo", "crop", "context", "answer"] as const;
export type StepId = (typeof STEP_IDS)[number];
export const STEP_PATH: Record<StepId, string> = {
  photo: "/",
  crop: "/culture",
  context: "/precisions",
  answer: "/reponse",
};

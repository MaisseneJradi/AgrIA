import { within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectLogicalDirectionOnly, renderIn } from "@/test/utils";
import { Skeleton, SkeletonBlock } from "./Skeleton";

describe.each(["fr", "ar"] as const)("Skeleton (%s)", (lang) => {
  it("the grey lines are hidden, the loading is announced once in the language of the page", async () => {
    const { container } = await renderIn(
      lang,
      <>
        <Skeleton className="h-4" />
        <SkeletonBlock lines={3} />
      </>,
    );
    const status = within(container).getByRole("status");
    expect(status).toHaveTextContent(lang === "fr" ? "Chargement…" : "جارٍ التحميل…");
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(4);
    expectLogicalDirectionOnly(container);
  });
});

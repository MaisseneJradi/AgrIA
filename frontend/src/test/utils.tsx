import { render, type RenderOptions } from "@testing-library/react";
import { act, type ReactElement } from "react";
import { expect } from "vitest";
import { ToastProvider } from "@/components/ui";
import { setLang, type Lang } from "@/lib/i18n";

/** Render in a language: lang and dir set on <html> as in the app. withToast: inside the ToastProvider (its live
 * region is a role "status" of its own). */
export async function renderIn(
  lang: Lang,
  ui: ReactElement,
  options?: RenderOptions & { withToast?: boolean },
) {
  await act(async () => {
    await setLang(lang);
  });
  return render(options?.withToast ? <ToastProvider>{ui}</ToastProvider> : ui, options);
}

// Physical left / right classes break right-to-left: components use the logical ones (ms-, me-, ps-, pe-, start-,
// end-, text-start, border-s...). Every component test runs this check.
const PHYSICAL =
  /(^|\s|:)-?(ml|mr|pl|pr|left|right|rounded-l|rounded-r|rounded-tl|rounded-tr|rounded-bl|rounded-br|border-l|border-r|text-left|text-right|scroll-ml|scroll-mr)(-|\s|$)/;

export function expectLogicalDirectionOnly(container: HTMLElement) {
  const all = [container, ...Array.from(container.querySelectorAll<HTMLElement>("*"))];
  const bad = all
    .map((el) => (typeof el.className === "string" ? el.className : (el.getAttribute("class") ?? "")))
    .filter((c) => PHYSICAL.test(c));
  expect(bad).toEqual([]);
}

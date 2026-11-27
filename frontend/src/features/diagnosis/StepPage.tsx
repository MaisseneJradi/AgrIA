import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Stepper } from "@/components/ui";
import { STEP_IDS, type StepId } from "./steps";

/** One step of the flow: where we are, a title that gets the focus when the step opens (screen readers and keyboard
 * start at the top of the new step), the content, then the actions at the bottom of the screen. */
export function StepPage({
  step,
  title,
  children,
  actions,
}: {
  step: StepId;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const { t } = useTranslation();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [step]);
  const steps = STEP_IDS.map((id) => ({ id, label: t(`steps.${id}`) }));
  return (
    <div className="space-y-5 pb-28 print:pb-0">
      <Stepper steps={steps} current={STEP_IDS.indexOf(step)} className="print:hidden" />
      <h1
        ref={heading}
        tabIndex={-1}
        className="text-2xl font-bold leading-tight focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 sm:text-3xl"
      >
        {title}
      </h1>
      {children}
      {actions && (
        <div className="fixed inset-x-0 bottom-0 z-20 print:hidden border-t border-border bg-bg/95 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur">
          <div className="mx-auto flex max-w-3xl gap-3">{actions}</div>
        </div>
      )}
    </div>
  );
}

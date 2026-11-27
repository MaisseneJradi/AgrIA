import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

export interface BottomSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
}

/** A panel that slides up from the bottom (the list of crops...). Radix Dialog: focus kept inside, Escape and the
 * backdrop close it. Opened from outside (no Dialog.Trigger), so the element focused when it opens is kept and gets
 * the focus back when it closes (Radix alone would leave it on the page body). */
export function BottomSheet({ open, onOpenChange, title, description, children }: BottomSheetProps) {
  const { t } = useTranslation();
  const opener = useRef<HTMLElement | null>(null);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          onOpenAutoFocus={() => {
            opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
          }}
          onCloseAutoFocus={(e) => {
            if (opener.current?.isConnected) {
              e.preventDefault();
              opener.current.focus();
            }
          }}
          className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[85vh] w-full max-w-xl animate-sheet-in flex-col rounded-t-3xl bg-surface p-4 pb-[max(1rem,env(safe-area-inset-bottom))] text-text shadow-card"
        >
          <span aria-hidden="true" className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-border" />
          <div className="mb-2 flex items-center gap-2">
            <Dialog.Title className="flex-1 font-display text-xl font-semibold">{title}</Dialog.Title>
            <Dialog.Close
              aria-label={t("common.close")}
              className="grid min-h-touch min-w-touch place-items-center rounded-full hover:bg-surface-2"
            >
              <X className="size-6" aria-hidden="true" />
            </Dialog.Close>
          </div>
          <Dialog.Description className={description ? "mb-3 text-muted" : "sr-only"}>
            {description ?? title}
          </Dialog.Description>
          <div className="overflow-y-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

"use client";

import { useRef } from "react";

type AutoFocusHandler = ((event: Event) => void) | undefined;

// When a dialog closes because the next dialog of the same flow opened, such as a review step,
// the next dialog takes over the control that focus should finally return to.
const handedOver = new WeakMap<object, HTMLElement>();

// Radix returns focus to a Dialog Trigger when a dialog closes. Most COMPASS dialogs open from a
// button that sets state instead, and focus would otherwise fall back to the page. This remembers
// what had focus when the dialog opened and returns focus there after it closes, unless the
// consumer placed focus itself or something else, such as the next dialog, has already taken it.
export function useDialogReturnFocus(
  onOpenAutoFocus: AutoFocusHandler,
  onCloseAutoFocus: AutoFocusHandler,
) {
  const opener = useRef<HTMLElement | null>(null);

  return {
    onOpenAutoFocus(event: Event) {
      const active = document.activeElement;
      opener.current = active instanceof HTMLElement && active !== document.body ? active : null;
      onOpenAutoFocus?.(event);
    },
    onCloseAutoFocus(event: Event) {
      onCloseAutoFocus?.(event);
      const own = opener.current?.isConnected ? opener.current : null;
      const target = own ?? (event.target ? handedOver.get(event.target) : undefined);
      opener.current = null;
      if (event.defaultPrevented || !target?.isConnected) return;
      const active = document.activeElement;
      if (active && active !== document.body) {
        const nextDialog = active.closest('[role="dialog"], [role="alertdialog"]');
        if (nextDialog) handedOver.set(nextDialog, target);
        return;
      }
      target.focus();
    },
  };
}

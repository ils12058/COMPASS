"use client";

import type { ReactNode } from "react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";

export function ConfirmationDialog({
  triggerLabel,
  title,
  children,
  confirmLabel,
  confirmVariant = "primary",
  pendingLabel,
  isPending,
  disabled,
  onConfirm,
}: {
  triggerLabel: string;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  confirmVariant?: "primary" | "destructive";
  pendingLabel: string;
  isPending: boolean;
  disabled?: boolean;
  onConfirm: () => void | Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  function open() {
    returnFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.showModal();
    window.requestAnimationFrame(() => headingRef.current?.focus());
  }

  function close() {
    if (!isPending) {
      dialogRef.current?.close();
    }
  }

  async function confirm() {
    try {
      await onConfirm();
      if (dialogRef.current?.open) {
        dialogRef.current.close();
      }
    } catch {
      // The parent mutation surface owns the safe error message.
    }
  }

  return (
    <>
      <Button
        variant={confirmVariant === "destructive" ? "destructive" : "primary"}
        onClick={open}
        disabled={disabled || isPending}
      >
        {triggerLabel}
      </Button>

      <dialog
        ref={dialogRef}
        aria-labelledby="content-confirmation-title"
        className="m-auto w-[min(92vw,34rem)] rounded-2xl border bg-card p-0 text-foreground shadow-md backdrop:bg-black/35"
        onClick={(event) => {
          if (event.target === dialogRef.current) {
            close();
          }
        }}
        onClose={() => returnFocusRef.current?.focus()}
      >
        <div className="p-6 sm:p-7">
          <h2
            ref={headingRef}
            id="content-confirmation-title"
            tabIndex={-1}
            className="font-heading text-2xl font-bold"
          >
            {title}
          </h2>
          <div className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
            {children}
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <Button variant="outline" onClick={close} disabled={isPending}>
              Cancel
            </Button>
            <Button
              variant={confirmVariant === "destructive" ? "destructive" : "primary"}
              onClick={() => void confirm()}
              disabled={isPending}
            >
              {isPending ? pendingLabel : confirmLabel}
            </Button>
          </div>
        </div>
      </dialog>
    </>
  );
}

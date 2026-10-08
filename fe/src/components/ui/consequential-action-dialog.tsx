"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

// What the dialog says after the backend confirmed the action, when the outcome deserves an
// acknowledgment in place rather than the dialog closing on its own.
export type ConsequentialActionCompletion = {
  title: string;
  children: ReactNode;
  doneLabel?: string;
};

// The completed state's only control. Focus moves to it when the outcome replaces the
// confirmation, and it is described by the outcome, so a screen reader hears what happened.
function CompletionDone({ label, describedBy }: { label: string; describedBy: string }) {
  const done = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    done.current?.focus();
  }, []);
  return (
    <AlertDialogCancel asChild>
      <Button ref={done} type="button" aria-describedby={describedBy}>
        {label}
      </Button>
    </AlertDialogCancel>
  );
}

function CompletionBody({ completion }: { completion: ConsequentialActionCompletion }) {
  const outcomeId = useId();
  return (
    <>
      <AlertDialogDescription asChild>
        <div id={outcomeId} className="mt-2 space-y-3 text-sm leading-6 text-muted">
          {completion.children}
        </div>
      </AlertDialogDescription>
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <CompletionDone label={completion.doneLabel ?? "Done"} describedBy={outcomeId} />
      </div>
    </>
  );
}

// A confirmation for a consequential action: confirm → pending → error and retry, all in place.
// With `completed`, a confirmed success replaces the confirmation with its outcome and a single
// Done, so the same action cannot be submitted twice and the reader sees what happened where they
// acted. Without it, the feature closes the dialog on success as before.
export function ConsequentialActionDialog({
  open,
  title,
  children,
  confirmLabel,
  pendingLabel,
  pending,
  confirmDisabled = false,
  error,
  variant = "primary",
  cancelLabel = "Cancel",
  completed = null,
  choices,
  onOpenChange,
  onConfirm,
  onCloseAutoFocus,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  pendingLabel: string;
  pending: boolean;
  confirmDisabled?: boolean;
  error: string | null;
  variant?: "primary" | "danger";
  cancelLabel?: string;
  completed?: ConsequentialActionCompletion | null;
  // A choice that shapes the action, such as whether a transcript is saved. It sits after the
  // description, so the description stays plain text for assistive technology.
  choices?: ReactNode;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  // For a completed action whose opener is gone, such as the Remove button of a removed row.
  onCloseAutoFocus?: (event: Event) => void;
}) {
  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (pending) return;
        onOpenChange(next);
      }}
    >
      <AlertDialogContent
        aria-busy={pending}
        onEscapeKeyDown={(event) => {
          if (pending) event.preventDefault();
        }}
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <AlertDialogTitle className="break-words">{completed ? completed.title : title}</AlertDialogTitle>
        {completed ? (
          <CompletionBody completion={completed} />
        ) : (
          <>
            <AlertDialogDescription asChild>
              <div className="mt-2 space-y-3 text-sm leading-6 text-muted">
                {children}
              </div>
            </AlertDialogDescription>
            {choices ? <div className="mt-4">{choices}</div> : null}
            {error ? (
              <p role="alert" className="mt-4 text-sm leading-6 text-danger">
                {error}
              </p>
            ) : null}
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <AlertDialogCancel asChild>
                <Button type="button" variant="secondary" disabled={pending}>
                  {cancelLabel}
                </Button>
              </AlertDialogCancel>
              <Button
                type="button"
                variant={variant}
                disabled={pending || confirmDisabled}
                onClick={onConfirm}
              >
                {pending ? pendingLabel : confirmLabel}
              </Button>
            </div>
          </>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}

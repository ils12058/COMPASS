"use client";

import type { ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

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
  onOpenChange,
  onConfirm,
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
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
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
      >
        <AlertDialogTitle className="break-words">{title}</AlertDialogTitle>
        <AlertDialogDescription asChild>
          <div className="mt-2 space-y-3 text-sm leading-6 text-muted">
            {children}
          </div>
        </AlertDialogDescription>
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
      </AlertDialogContent>
    </AlertDialog>
  );
}

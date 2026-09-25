"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { StepUpDialog } from "@/features/account/security/security-shared";
import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
} from "@/lib/api/errors";

const knownErrors: Record<string, string> = {
  email_delivery_not_found: "This email delivery is no longer available.",
  email_delivery_not_retryable:
    "This email delivery cannot be retried in its current state.",
  invalid_email_delivery_request:
    "The email retry request was not accepted. Refresh the list and try again.",
  invalid_maintenance_window:
    "The maintenance window must start in the future and end after it starts.",
  invalid_maintenance_request:
    "The maintenance request contains a value that is not accepted.",
  maintenance_already_enabled: "Maintenance Mode is already active.",
  maintenance_not_enabled: "Manual Maintenance Mode is not active.",
  maintenance_schedule_conflict:
    "The requested change conflicts with the configured maintenance schedule. Review the current state and try again.",
  maintenance_schedule_not_found:
    "The maintenance schedule is no longer available. Refresh the page and try again.",
  permission_denied: "You do not have permission to perform this Platform action.",
  recent_mfa_required: "Recent authenticator verification is required.",
};

export function platformErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownErrors[code]) || readApiErrorMessage(error.body) || fallback;
}

export function usePlatformAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    onStepUpRequired?: () => void,
  ): Promise<boolean> {
    setError(null);
    setNotice(null);
    try {
      await operation();
      return true;
    } catch (caught) {
      if (
        caught instanceof CompassApiError &&
        readApiErrorCode(caught.body) === "recent_mfa_required"
      ) {
        onStepUpRequired?.();
        setNotice(
          "Recent authenticator verification is required. Verify, then submit and confirm the action again.",
        );
        setStepUpOpen(true);
      } else {
        setError(platformErrorMessage(caught, fallback));
      }
      return false;
    }
  }

  const stepUpDialog = (
    <StepUpDialog
      open={stepUpOpen}
      onOpenChange={setStepUpOpen}
      onVerified={() =>
        setNotice(
          "Verification complete. Submit and confirm the action again to continue.",
        )
      }
    />
  );

  return {
    error,
    notice,
    setError,
    setNotice,
    run,
    stepUpDialog,
  };
}

export function PlatformConfirmation({
  open,
  title,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  pendingLabel,
  pending,
  error,
  variant = "primary",
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  pendingLabel: string;
  pending: boolean;
  error: string | null;
  variant?: "primary" | "danger";
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!pending) onOpenChange(next);
      }}
    >
      <AlertDialogContent
        onEscapeKeyDown={(event) => {
          if (pending) event.preventDefault();
        }}
      >
        <AlertDialogTitle>{title}</AlertDialogTitle>
        <AlertDialogDescription asChild>
          <div className="mt-2 space-y-3 text-sm leading-6 text-muted">
            {children}
          </div>
        </AlertDialogDescription>
        {error ? (
          <p role="alert" className="mt-4 text-sm text-danger">
            {error}
          </p>
        ) : null}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <AlertDialogCancel asChild>
            <Button
              variant="secondary"
              disabled={pending}
              onClick={() => onOpenChange(false)}
            >
              {cancelLabel}
            </Button>
          </AlertDialogCancel>
          <Button
            variant={variant}
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? pendingLabel : confirmLabel}
          </Button>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}

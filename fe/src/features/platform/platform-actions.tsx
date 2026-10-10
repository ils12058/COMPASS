"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { StepUpDialog } from "@/features/account/security/security-shared";
import {
  stepUpNotice,
  stepUpRequirement,
  type StepUpRequirement,
} from "@/features/account/security/step-up";
import {
  CompassApiError,
  readApiErrorCode,
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
    "Some maintenance details need attention. Review them and try again.",
  maintenance_already_enabled: "Maintenance Mode is already active.",
  maintenance_not_enabled: "Manual Maintenance Mode is not active.",
  maintenance_schedule_conflict:
    "This change conflicts with the current maintenance schedule. Review the schedule and try again.",
  maintenance_schedule_not_found:
    "The maintenance schedule is no longer available. Refresh the page and try again.",
  permission_denied: "You can't perform this Platform Operations action.",
};

export function platformErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownErrors[code]) || fallback;
}

export function usePlatformAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [stepUp, setStepUp] = useState<StepUpRequirement>("verify");

  // Maintenance changes keep step-up; email retry does not need it.
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
      const requirement = stepUpRequirement(caught);
      if (requirement) {
        onStepUpRequired?.();
        setStepUp(requirement);
        setNotice(stepUpNotice(requirement));
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
      requirement={stepUp}
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
    <ConsequentialActionDialog
      open={open}
      title={title}
      confirmLabel={confirmLabel}
      cancelLabel={cancelLabel}
      pendingLabel={pendingLabel}
      pending={pending}
      error={error}
      variant={variant}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
    >
      {children}
    </ConsequentialActionDialog>
  );
}

"use client";

import { useState } from "react";

import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import {
  CompassApiError,
  readApiErrorCode,
} from "@/lib/api/errors";

const knownErrors: Record<string, string> = {
  permission_denied: "You can't manage organization records.",
  organization_not_found: "This organization record is unavailable.",
  organization_conflict:
    "This change conflicts with an existing assignment or active organization structure. Review the details and try again.",
  invalid_organization_request:
    "The selected organization record cannot be used for this action. Review your selection and try again.",
};

export function organizationErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownErrors[code]) || fallback;
}

export function useOrganizationAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const continuation = useStepUpContinuation();

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    options?: {
      onStepUpRequired?: () => void;
    },
  ): Promise<T | undefined> {
    setError(null);
    setNotice(null);
    const result = await continuation.run(operation, {
      onStepUpRequired: options?.onStepUpRequired,
      onFailure: (caught) => {
        setError(organizationErrorMessage(caught, fallback));
      },
    });
    if (result !== undefined) setNotice(null);
    return result;
  }

  const visibleNotice = notice ?? continuation.notice;
  const messages = (
    <>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {visibleNotice ? (
        <p role="status" className="mt-4 text-sm text-muted">
          {visibleNotice}
        </p>
      ) : null}
    </>
  );

  const stepUpDialog = (
    <StepUpDialog
      open={continuation.open}
      requirement={continuation.requirement}
      onOpenChange={continuation.setOpen}
      isContinuing={continuation.isContinuing}
      onVerified={continuation.continueAfterVerification}
    />
  );

  return {
    error,
    notice: visibleNotice,
    setError,
    setNotice,
    run,
    messages,
    stepUpDialog,
  };
}

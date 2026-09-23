"use client";

import { useState } from "react";

import { StepUpDialog } from "@/features/account/security/security-shared";
import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
} from "@/lib/api/errors";

const knownErrors: Record<string, string> = {
  permission_denied: "You do not have permission to manage Organization.",
  organization_not_found: "The selected Organization record is no longer available.",
  organization_conflict:
    "This change conflicts with an existing Organization relationship or active structure.",
  invalid_organization_request:
    "The selected Organization value is no longer eligible for this action.",
  recent_mfa_required: "Recent authenticator verification is required.",
};

export function organizationErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const backendMessage = readApiErrorMessage(error.body);
  if (
    code === "organization_conflict" ||
    code === "invalid_organization_request" ||
    code === "organization_not_found"
  ) {
    return backendMessage ?? knownErrors[code] ?? fallback;
  }
  return (code && knownErrors[code]) || backendMessage || fallback;
}

export function useOrganizationAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [afterStepUp, setAfterStepUp] = useState<(() => void) | null>(null);

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    options?: {
      onStepUpRequired?: () => void;
      onStepUpVerified?: () => void;
    },
  ): Promise<T | undefined> {
    setError(null);
    setNotice(null);
    try {
      return await operation();
    } catch (caught) {
      const code =
        caught instanceof CompassApiError
          ? readApiErrorCode(caught.body)
          : undefined;
      if (code === "recent_mfa_required") {
        options?.onStepUpRequired?.();
        setAfterStepUp(() => options?.onStepUpVerified ?? null);
        setNotice("Verify your authenticator, then submit the action again.");
        setStepUpOpen(true);
      } else {
        setError(organizationErrorMessage(caught, fallback));
      }
      return undefined;
    }
  }

  const messages = (
    <>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="mt-4 text-sm text-success">
          {notice}
        </p>
      ) : null}
    </>
  );

  const stepUpDialog = (
    <StepUpDialog
      open={stepUpOpen}
      onOpenChange={setStepUpOpen}
      onVerified={() => {
        setNotice("Verification complete. Submit the action again to continue.");
        const resume = afterStepUp;
        setAfterStepUp(null);
        resume?.();
      }}
    />
  );

  return {
    error,
    notice,
    setError,
    setNotice,
    run,
    messages,
    stepUpDialog,
  };
}

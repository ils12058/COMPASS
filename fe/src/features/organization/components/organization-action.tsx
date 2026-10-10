"use client";

import { useState } from "react";

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
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [stepUp, setStepUp] = useState<StepUpRequirement>("verify");
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
      const requirement = stepUpRequirement(caught);
      if (requirement) {
        setStepUp(requirement);
        options?.onStepUpRequired?.();
        setAfterStepUp(() => options?.onStepUpVerified ?? null);
        setNotice(stepUpNotice(requirement));
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
      requirement={stepUp}
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

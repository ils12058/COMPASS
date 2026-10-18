"use client";

import { useState } from "react";

import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";

const knownErrors: Record<string, string> = {
  academic_year_not_found: "The selected Academic Year is no longer available.",
  academic_year_conflict:
    "This change conflicts with the current academic-year setup. Review the label and current year before trying again.",
  invalid_academic_year_request:
    "Check the Academic Year label and try again.",
  institutional_form_not_found:
    "The selected Form Family or Form Revision is no longer available.",
  permission_denied:
    "You can't make this institutional change.",
};

export function institutionConfigurationErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;

  const code = readApiErrorCode(error.body);
  return (code && knownErrors[code]) || fallback;
}

type StepUpOptions = {
  onStepUpRequired?: () => void;
};

export function useInstitutionConfigurationAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const continuation = useStepUpContinuation();

  function resetFeedback() {
    setError(null);
    setNotice(null);
  }

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    options?: StepUpOptions,
  ): Promise<T | undefined> {
    resetFeedback();
    const result = await continuation.run(operation, {
      onStepUpRequired: options?.onStepUpRequired,
      onFailure: (caught) => {
        setError(institutionConfigurationErrorMessage(caught, fallback));
      },
    });
    if (result !== undefined) setNotice(null);
    return result;
  }

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
    notice: notice ?? continuation.notice,
    resetFeedback,
    run,
    setError,
    stepUpDialog,
  };
}

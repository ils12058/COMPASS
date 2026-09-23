"use client";

import { useRef, useState } from "react";

import { StepUpDialog } from "@/features/account/security/security-shared";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

const knownErrors: Record<string, string> = {
  academic_year_not_found: "The selected Academic Year is no longer available.",
  academic_year_conflict:
    "This Academic Year change conflicts with the current configuration.",
  invalid_academic_year_request:
    "Check the Academic Year label and try again.",
  institutional_form_not_found:
    "The selected Form Family or Form Revision is no longer available.",
  institutional_form_conflict:
    "This Form Revision change conflicts with the current configuration.",
  invalid_institutional_form_request:
    "The Form Revision metadata was not accepted. Check the values and try again.",
  permission_denied:
    "Your current access does not allow this Institution configuration change.",
};

export function institutionConfigurationErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;

  const code = readApiErrorCode(error.body);
  const backendMessage = readApiErrorMessage(error.body);
  if (code && knownErrors[code]) {
    return backendMessage ?? knownErrors[code];
  }
  return backendMessage ?? fallback;
}

type StepUpOptions = {
  onStepUpRequired?: () => void;
  onStepUpVerified?: () => void;
};

export function useInstitutionConfigurationAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const restoreInteraction = useRef<(() => void) | null>(null);

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
    try {
      return await operation();
    } catch (caught) {
      const code =
        caught instanceof CompassApiError
          ? readApiErrorCode(caught.body)
          : undefined;
      if (code === "recent_mfa_required") {
        options?.onStepUpRequired?.();
        restoreInteraction.current = options?.onStepUpVerified ?? null;
        setNotice(
          "Verify your authenticator. The action will not be submitted automatically.",
        );
        setStepUpOpen(true);
      } else {
        setError(institutionConfigurationErrorMessage(caught, fallback));
      }
      return undefined;
    }
  }

  const stepUpDialog = (
    <StepUpDialog
      open={stepUpOpen}
      onOpenChange={setStepUpOpen}
      onVerified={() => {
        setNotice("Verification complete. Submit or confirm the action again.");
        const restore = restoreInteraction.current;
        restoreInteraction.current = null;
        restore?.();
      }}
    />
  );

  return {
    error,
    notice,
    resetFeedback,
    run,
    setError,
    stepUpDialog,
  };
}

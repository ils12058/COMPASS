"use client";

import { useCallback, useState } from "react";

import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import { rosterError } from "@/features/student-academics/roster-import/roster-import-presentation";

export function useRosterImportAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const {
    run: runContinuation,
    requirement,
    open,
    setOpen,
    isContinuing,
    notice: continuationNotice,
    continueAfterVerification,
  } = useStepUpContinuation();

  const run = useCallback(
    async <T,>(
      operation: () => Promise<T>,
      fallback: string,
      onStepUpRequired?: () => void,
      onFailure?: (error: unknown) => void,
    ): Promise<T | undefined> => {
      setError(null);
      setNotice(null);
      const result = await runContinuation(operation, {
        onStepUpRequired,
        onFailure: (caught) => {
          setError(rosterError(caught, fallback));
          onFailure?.(caught);
        },
      });
      if (result !== undefined) setNotice(null);
      return result;
    },
    [runContinuation],
  );

  return {
    error,
    notice,
    setError,
    setNotice,
    run,
    stepUp: requirement,
    stepUpOpen: open,
    setStepUpOpen: setOpen,
    isContinuing,
    continuationNotice,
    continueAfterVerification,
  };
}

export function RosterImportFeedback({
  action,
  showMessages = true,
}: {
  action: ReturnType<typeof useRosterImportAction>;
  showMessages?: boolean;
}) {
  return (
    <>
      {showMessages && action.error ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {action.error}
        </p>
      ) : null}
      {showMessages && (action.notice || action.continuationNotice) ? (
        <p role="status" className="mt-4 text-sm text-muted">
          {action.notice ?? action.continuationNotice}
        </p>
      ) : null}
      <StepUpDialog
        open={action.stepUpOpen}
        requirement={action.stepUp}
        onOpenChange={action.setStepUpOpen}
        isContinuing={action.isContinuing}
        onVerified={action.continueAfterVerification}
      />
    </>
  );
}

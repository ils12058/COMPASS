"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { accountErrorCode } from "@/features/account/components/account-errors";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import {
  getAccountsGetEffectiveAccessQueryKey,
  getAccountsGetQueryKey,
  getAccountsListCapabilityOverridesQueryKey,
  getAccountsListDesignationsQueryKey,
  getAccountsListQueryKey,
} from "@/lib/api/generated/accounts/accounts";
import { CompassApiError } from "@/lib/api/errors";

const knownErrors: Record<string, string> = {
  permission_denied: "You do not have permission to manage accounts.",
  institutional_designation_permission_denied:
    "You do not have permission to manage institutional designations.",
  last_account_manager:
    "COMPASS must retain an active account manager. Assign another manager before making this change.",
  identity_policy_unavailable:
    "Account policy is temporarily unavailable. Try again later.",
  self_target_forbidden:
    "You cannot perform this administrative action on your own account.",
  rate_limited: "Too many attempts. Try again later.",
  security_unavailable:
    "This security action is temporarily unavailable. Try again later.",
};

export function managedAccountError(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = accountErrorCode(error);
  if (code && knownErrors[code]) return knownErrors[code];
  return fallback;
}

export function useManagedAction() {
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
          setError(managedAccountError(caught, fallback));
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

export function ManagedActionFeedback({
  action,
  showMessages = true,
}: {
  action: ReturnType<typeof useManagedAction>;
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

export function useInvalidateManagedAccount(userId?: string) {
  const client = useQueryClient();
  return useCallback(async () => {
    await client.invalidateQueries({ queryKey: getAccountsListQueryKey() });
    if (!userId) return;
    await Promise.all([
      client.invalidateQueries({ queryKey: getAccountsGetQueryKey(userId) }),
      client.invalidateQueries({
        queryKey: getAccountsGetEffectiveAccessQueryKey(userId),
      }),
      client.invalidateQueries({
        queryKey: getAccountsListCapabilityOverridesQueryKey(userId),
      }),
      client.invalidateQueries({
        queryKey: getAccountsListDesignationsQueryKey(userId),
      }),
    ]);
  }, [client, userId]);
}

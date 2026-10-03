"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { accountErrorCode } from "@/features/account/components/account-errors";
import { StepUpDialog } from "@/features/account/security/security-shared";
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
  recent_mfa_required: "Recent authenticator verification is required.",
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
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [afterStepUp, setAfterStepUp] = useState<(() => void) | null>(null);

  const run = useCallback(
    async <T,>(
      operation: () => Promise<T>,
      fallback: string,
      onStepUpRequired?: () => void,
      onFailure?: (error: unknown) => void,
      onStepUpVerified?: () => void,
    ): Promise<T | undefined> => {
      setError(null);
      setNotice(null);
      try {
        return await operation();
      } catch (caught) {
        if (accountErrorCode(caught) === "recent_mfa_required") {
          onStepUpRequired?.();
          setAfterStepUp(() => onStepUpVerified ?? null);
          setStepUpOpen(true);
          setNotice("Verify your authenticator, then submit the action again.");
        } else {
          setError(managedAccountError(caught, fallback));
          onFailure?.(caught);
        }
        return undefined;
      }
    },
    [],
  );

  return {
    error,
    notice,
    setError,
    setNotice,
    run,
    stepUpOpen,
    setStepUpOpen,
    afterStepUp,
    setAfterStepUp,
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
      {showMessages && action.notice ? (
        <p role="status" className="mt-4 text-sm text-success">
          {action.notice}
        </p>
      ) : null}
      <StepUpDialog
        open={action.stepUpOpen}
        onOpenChange={action.setStepUpOpen}
        onVerified={() => {
          action.setNotice(
            "Verification complete. Review and confirm the action again to continue.",
          );
          const resume = action.afterStepUp;
          action.setAfterStepUp(null);
          resume?.();
        }}
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

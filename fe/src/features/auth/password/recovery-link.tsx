"use client";

import { useQuery } from "@tanstack/react-query";
import { useId, useState, useSyncExternalStore, type FormEvent } from "react";

import { authErrorMessage, passwordPolicyMessages } from "@/features/auth/utils/errors";
import { RecoveryLinkView, type RecoveryPageState } from "@/features/auth/password/recovery-link-view";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { authVerifyRecoveryLink, useAuthConfirmRecoveryLink } from "@/lib/api/generated/auth/auth";

// The fragment is never sent to Next.js, a proxy, or the backend in an HTTP URL.
function readFragment() { return window.location.hash.slice(1); }
function subscribeFragment(notify: () => void) {
  window.addEventListener("hashchange", notify);
  return () => window.removeEventListener("hashchange", notify);
}
function serverFragment() { return null; }

export function RecoveryLink() {
  const token = useSyncExternalStore(subscribeFragment, readFragment, serverFragment);
  if (token === null) return <RecoveryLinkView state={{ kind: "loading" }} />;
  if (!token) return <RecoveryLinkView state={{ kind: "unavailable" }} />;
  return <RecoveryLinkForm key={token} token={token} />;
}

function RecoveryLinkForm({ token }: { token: string }) {
  const instance = useId();
  const check = useQuery({
    // Secret-free cache key; the component remounts if the link fragment changes.
    queryKey: ["account-recovery-check", instance],
    queryFn: () => authVerifyRecoveryLink({ token }),
    retry: false, gcTime: 0, staleTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  const complete = useAuthConfirmRecoveryLink({ mutation: { gcTime: 0, retry: false } });
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [policy, setPolicy] = useState<string[]>([]);
  const [outcome, setOutcome] = useState<RecoveryPageState | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (complete.isPending) return;
    setError(null); setPolicy([]);
    if (newPassword !== confirmPassword) { setError("The new passwords do not match."); return; }
    try {
      const response = await complete.mutateAsync({ data: { token, new_password: newPassword } });
      if (!response.data.password_set) { setError("Couldn't confirm the password update. Try again."); return; }
      setNewPassword(""); setConfirmPassword("");
      setOutcome({ kind: "success", emailChange: check.data?.data.email_change ?? false });
    } catch (caught) {
      if (caught instanceof CompassApiError && readApiErrorCode(caught.body) === "account_recovery_invalid") {
        setNewPassword(""); setConfirmPassword(""); setOutcome({ kind: "unavailable" });
      } else {
        const issues = passwordPolicyMessages(caught); setPolicy(issues);
        setError(issues.length ? "Review the password requirements below." : authErrorMessage(caught, "Couldn't confirm the password update. Try again."));
      }
    } finally { complete.reset(); }
  }

  let state: RecoveryPageState;
  if (outcome) state = outcome;
  else if (check.isPending) state = { kind: "loading" };
  else if (check.isError) state = check.error instanceof CompassApiError && readApiErrorCode(check.error.body) === "account_recovery_invalid"
    ? { kind: "unavailable" } : { kind: "error", message: authErrorMessage(check.error, "Couldn't check this link. Try again.") };
  else state = check.data.data.valid ? { kind: "valid", details: check.data.data } : { kind: "unavailable" };
  return <RecoveryLinkView state={state} newPassword={newPassword} confirmPassword={confirmPassword}
    error={error} policyMessages={policy} pending={complete.isPending} onPasswordChange={setNewPassword}
    onConfirmChange={setConfirmPassword} onSubmit={submit} onRetry={() => void check.refetch()} />;
}

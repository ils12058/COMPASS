"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/features/auth/components/password-input";
import { passwordPolicyMessages } from "@/features/auth/utils/errors";
import { accountErrorCode, accountErrorMessage } from "@/features/account/components/account-errors";
import { SecurityBackLink, StepUpDialog } from "@/features/account/security/security-shared";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  getAuthListSessionsQueryKey,
  useAuthChangePassword,
  useAuthGetMfaStatus,
} from "@/lib/api/generated/auth/auth";

export function PasswordChangePage() {
  const queryClient = useQueryClient();
  const mfa = useAuthGetMfaStatus({ query: { retry: false } });
  const change = useAuthChangePassword();
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [verified, setVerified] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [policyIssues, setPolicyIssues] = useState<string[]>([]);
  const [changed, setChanged] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const usesMfa = mfa.data?.data.enabled ?? false;
  const recent = mfa.data?.data.recent || verified;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPolicyIssues([]);
    if (newPassword !== confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    if (usesMfa && !recent) {
      setStepUpOpen(true);
      return;
    }
    try {
      const response = await change.mutateAsync({ data: {
        new_password: newPassword,
        ...(!usesMfa ? { current_password: currentPassword } : {}),
      } });
      if (!response.data.changed) {
        setError("The password could not be changed. Please try again.");
        return;
      }
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setChanged(true);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getAuthListSessionsQueryKey() }),
      ]);
    } catch (caught) {
      const code = accountErrorCode(caught);
      if (code === "recent_mfa_required") {
        setStepUpOpen(true);
        return;
      }
      if (code === "mfa_setup_required") setSetupRequired(true);
      const issues = passwordPolicyMessages(caught);
      setPolicyIssues(issues);
      setError(issues.length ? "The new password does not meet the password policy." : accountErrorMessage(caught, "The password could not be changed. Please try again."));
    }
  }

  return (
    <section aria-labelledby="password-heading" className="max-w-2xl">
      <SecurityBackLink />
      <h1 id="password-heading" className="font-heading text-3xl font-bold text-ink">Change password</h1>
      {mfa.isPending ? <p role="status" className="mt-7 text-sm text-muted">Checking security requirements…</p> : null}
      {mfa.isError ? <div className="mt-7" role="alert"><p className="text-sm text-danger">Security requirements could not be loaded.</p><Button className="mt-3" variant="secondary" onClick={() => void mfa.refetch()}>Retry</Button></div> : null}
      {mfa.isSuccess ? (
        <form className="mt-7 space-y-5" onSubmit={submit}>
          {usesMfa && !recent ? <p className="text-sm leading-6 text-muted">Verify with your authenticator app before changing your password.</p> : null}
          {!usesMfa ? <div className="grid gap-2"><Label htmlFor="current-password">Current password</Label><PasswordInput id="current-password" name="current-password" autoComplete="current-password" required value={currentPassword} onChange={(event) => { setCurrentPassword(event.target.value); setChanged(false); }} /></div> : null}
          <div className="grid gap-2"><Label htmlFor="account-new-password">New password</Label><PasswordInput id="account-new-password" name="new-password" autoComplete="new-password" required value={newPassword} onChange={(event) => { setNewPassword(event.target.value); setChanged(false); }} /></div>
          <div className="grid gap-2"><Label htmlFor="account-confirm-password">Confirm new password</Label><PasswordInput id="account-confirm-password" name="confirm-password" autoComplete="new-password" required value={confirmation} onChange={(event) => { setConfirmation(event.target.value); setChanged(false); }} aria-describedby={error ? "password-change-error" : undefined} /></div>
          {error ? <p id="password-change-error" role="alert" className="text-sm text-danger">{error}</p> : null}
          {policyIssues.length ? <ul className="list-disc space-y-1 pl-5 text-sm text-danger">{policyIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : null}
          {setupRequired ? <Link href="/portal/account/security/authenticator" className="inline-flex min-h-10 items-center font-semibold text-brand hover:underline">Set up authenticator</Link> : null}
          {changed ? <p role="status" className="text-sm text-success">Password changed. Your current session remains signed in.</p> : null}
          <Button type="submit" disabled={change.isPending}>{change.isPending ? "Changing password…" : usesMfa && !recent ? "Verify to continue" : "Change password"}</Button>
        </form>
      ) : null}
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => setVerified(true)} />
    </section>
  );
}

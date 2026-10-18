"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { PasswordInput } from "@/features/auth/components/password-input";
import { passwordPolicyMessages } from "@/features/auth/utils/errors";
import { accountErrorMessage } from "@/features/account/components/account-errors";
import { SecurityBackLink, StepUpDialog } from "@/features/account/security/security-shared";
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
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
  const continuation = useStepUpContinuation();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [policyIssues, setPolicyIssues] = useState<string[]>([]);
  const [changed, setChanged] = useState(false);
  const usesMfa = mfa.data?.data.enabled ?? false;
  const recent = mfa.data?.data.recent ?? false;
  const credentialsRef = useRef({ currentPassword, newPassword });
  useEffect(() => {
    credentialsRef.current = { currentPassword, newPassword };
  }, [currentPassword, newPassword]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPolicyIssues([]);
    if (newPassword !== confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    const response = await continuation.run(
      () => change.mutateAsync({ data: {
        new_password: credentialsRef.current.newPassword,
        ...(!usesMfa ? { current_password: credentialsRef.current.currentPassword } : {}),
      } }),
      {
        onFailure: (caught) => {
      const issues = passwordPolicyMessages(caught);
      setPolicyIssues(issues);
      setError(issues.length ? "The new password does not meet the password policy." : accountErrorMessage(caught, "The password could not be changed. Please try again."));
        },
      },
    );
    if (!response) return;
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
  }

  return (
    <section aria-labelledby="password-heading" className="max-w-2xl">
      <SecurityBackLink />
      <PageHeader title="Change password" headingId="password-heading" />
      {mfa.isPending ? <RowsSkeleton label="Checking security requirements…" rows={2} framed /> : null}
      {mfa.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void mfa.refetch()}>Retry</Button>}>Security requirements could not be loaded.</Notice> : null}
      {mfa.isSuccess ? (
        <Panel as="div">
        <form onSubmit={submit}>
          <PanelBody className="space-y-5">
          {usesMfa && !recent ? <p className="text-sm leading-6 text-muted">You&apos;ll verify with your authenticator before your password changes.</p> : null}
          {!usesMfa ? <div className="grid gap-2"><Label htmlFor="current-password">Current password</Label><PasswordInput id="current-password" name="current-password" autoComplete="current-password" required value={currentPassword} onChange={(event) => { setCurrentPassword(event.target.value); setChanged(false); }} /></div> : null}
          <div className="grid gap-2"><Label htmlFor="account-new-password">New password</Label><PasswordInput id="account-new-password" name="new-password" autoComplete="new-password" required value={newPassword} onChange={(event) => { setNewPassword(event.target.value); setChanged(false); }} /></div>
          <div className="grid gap-2"><Label htmlFor="account-confirm-password">Confirm new password</Label><PasswordInput id="account-confirm-password" name="confirm-password" autoComplete="new-password" required value={confirmation} onChange={(event) => { setConfirmation(event.target.value); setChanged(false); }} aria-describedby={error ? "password-change-error" : undefined} /></div>
          {error ? <p id="password-change-error" role="alert" className="text-sm text-danger">{error}</p> : null}
          {continuation.notice ? <p role="status" className="text-sm text-muted">{continuation.notice}</p> : null}
          {policyIssues.length ? <ul className="list-disc space-y-1 pl-5 text-sm text-danger">{policyIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : null}
          {changed ? <p role="status" className="text-sm text-success">Password changed. Other sessions and trusted-browser access were revoked.</p> : null}
          </PanelBody>
          <PanelFooter>
            <Button type="submit" disabled={change.isPending}>{change.isPending ? "Changing password…" : usesMfa && !recent ? "Verify to continue" : "Change password"}</Button>
          </PanelFooter>
        </form>
        </Panel>
      ) : null}
      <StepUpDialog open={continuation.open} requirement={continuation.requirement} onOpenChange={continuation.setOpen} isContinuing={continuation.isContinuing} onVerified={continuation.continueAfterVerification} />
    </section>
  );
}

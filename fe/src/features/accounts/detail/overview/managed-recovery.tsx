"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { managedAccountError, useInvalidateManagedAccount } from "@/features/accounts/components/account-action";
import { useManagedAccount } from "@/features/accounts/detail/account-detail-frame";
import { accountName } from "@/features/accounts/presentation";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { stepUpRequirement, type StepUpRequirement } from "@/features/account/security/step-up";
import { isTurnstileConfigured, TurnstileWidget } from "@/features/auth/components/turnstile-widget";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { useAccountsRequestRecoveryLink, getAccountsGetQueryKey } from "@/lib/api/generated/accounts/accounts";
import { IdentityCheckCode } from "@/lib/api/generated/model";

export function ManagedRecovery() {
  const account = useManagedAccount();
  const { user } = usePortalSession();
  const invalidate = useInvalidateManagedAccount(account.id);
  const queryClient = useQueryClient();
  const request = useAccountsRequestRecoveryLink();
  const opener = useRef<HTMLButtonElement>(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [expectedVersion, setExpectedVersion] = useState(account.updated_at);
  const [basis, setBasis] = useState<IdentityCheckCode | "">("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [stepUp, setStepUp] = useState<StepUpRequirement | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [reset, setReset] = useState(0);
  const [refreshFailed, setRefreshFailed] = useState(false);
  async function refreshAccount() {
    try {
      await queryClient.refetchQueries({ queryKey: getAccountsGetQueryKey(account.id), exact: true }, { throwOnError: true });
      await invalidate();
      setRefreshFailed(false);
    } catch {
      setRefreshFailed(true);
      setError("Couldn't reload the account. Retry before sending a link.");
    }
  }
  const self = user.id === account.id;

  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!basis || (basis === IdentityCheckCode.other && !reason.trim())) return;
    setExpectedVersion(account.updated_at);
    setEntryOpen(false); setReviewOpen(true); setError(null);
  }

  async function send() {
    if (!basis || request.isPending || refreshFailed) return;
    setError(null);
    try {
      await request.mutateAsync({ userId: account.id, data: { new_email: email.trim(),
        identity_check_basis: basis, identity_check_reason: basis === IdentityCheckCode.other ? reason.trim() : "",
        expected_updated_at: expectedVersion,
        ...(isTurnstileConfigured ? { turnstile_token: token } : {}),
      } });
      setSent(true);
    } catch (caught) {
      const requirement = stepUpRequirement(caught);
      if (requirement) { setReviewOpen(false); setStepUp(requirement); return; }
      if (caught instanceof CompassApiError && readApiErrorCode(caught.body) === "account_recovery_conflict") {
        setError("Review the account details and new email before requesting another link.");
        setReviewOpen(false); setEntryOpen(true);
        // Keep entered values, refresh the authoritative version, require a new review.
        await refreshAccount();
      } else {
        setError(managedAccountError(caught, "Couldn't confirm that the link was sent. Review the details and try again."));
        if (isTurnstileConfigured) { setReviewOpen(false); setEntryOpen(true); }
      }
    } finally {
      if (isTurnstileConfigured) { setToken(null); setReset((current) => current + 1); }
    }
  }

  return <>
    <Panel aria-labelledby="managed-recovery-heading">
      <PanelHeader title="Account recovery" titleId="managed-recovery-heading" />
      <PanelBody>
        <p className="text-sm leading-6 text-muted">If the account holder lost access to their mailbox, check their identity before sending a recovery link to a new email.</p>
        {self ? <p className="mt-3 text-sm text-muted">You cannot recover your own account here.</p> : <>
          <Button ref={opener} className="mt-4 max-w-full whitespace-normal" variant="secondary" disabled={!account.is_active}
            onClick={() => { setEmail(""); setBasis(""); setReason(""); setError(null); setSent(false); setEntryOpen(true); }}>
            Change email and send recovery link
          </Button>
          {!account.is_active ? <p className="mt-3 text-sm text-muted">Enable this account before requesting a recovery link.</p> : null}
        </>}
      </PanelBody>
    </Panel>
    <Dialog open={entryOpen} onOpenChange={setEntryOpen}>
      <DialogContent onCloseAutoFocus={(event) => { event.preventDefault(); opener.current?.focus(); }}>
        <DialogTitle>Change email and send recovery link</DialogTitle>
        <DialogDescription>Record the identity check you completed for {accountName(account)}. COMPASS records your check; it does not verify identity.</DialogDescription>
        <form className="mt-5 space-y-4" onSubmit={review}>
          <p className="break-words text-sm text-muted">Current email: {account.email}</p>
          <div className="grid gap-2"><Label htmlFor="assisted-email">New email</Label>
            <Input id="assisted-email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></div>
          <div className="grid gap-2"><Label htmlFor="assisted-basis">Identity check</Label>
            <Select id="assisted-basis" required value={basis} onChange={(event) => {
              const selected = event.target.value;
              setBasis(selected === IdentityCheckCode.in_person_id || selected === IdentityCheckCode.other ? selected : "");
            }}>
              <option value="" disabled>Select how identity was checked</option>
              <option value={IdentityCheckCode.in_person_id}>Verified in person with a school or employee ID</option>
              <option value={IdentityCheckCode.other}>Other</option>
            </Select></div>
          {basis === IdentityCheckCode.other ? <div className="grid gap-2"><Label htmlFor="assisted-reason">How identity was checked</Label>
            <Input id="assisted-reason" required maxLength={240} value={reason} onChange={(event) => setReason(event.target.value)} /></div> : null}
          <TurnstileWidget action="email_otp" onTokenChange={setToken} resetKey={reset} />
          {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          {refreshFailed ? <Button variant="secondary" onClick={() => void refreshAccount()}>Retry</Button> : null}
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setEntryOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={refreshFailed || (isTurnstileConfigured && !token)}>Review recovery link</Button></div>
        </form>
      </DialogContent>
    </Dialog>
    <ConsequentialActionDialog open={reviewOpen} title={`Send a recovery link for ${accountName(account)}?`}
      confirmDisabled={isTurnstileConfigured && !token}
      confirmLabel="Send recovery link" pendingLabel="Sending recovery link…" pending={request.isPending}
      error={error} onConfirm={() => void send()}
      onCloseAutoFocus={(event) => { event.preventDefault(); opener.current?.focus(); }}
      completed={sent ? { title: "Recovery link sent", children: <p>A link was sent to <span className="break-all">{email}</span>. The account changes only when the account holder completes recovery.</p> } : null}
      onOpenChange={(open) => { setReviewOpen(open); if (!open) { setSent(false); opener.current?.focus(); } }}>
      <p>A single-use link will go to <span className="break-all font-semibold text-ink">{email}</span>. Earlier recovery links will stop working.</p>
      <p>When the account holder uses it, their sign-in email and password will change and all existing sign-ins will end. Their authenticator stays in place.</p>
      <p>Identity check: {basis === IdentityCheckCode.in_person_id ? "Verified in person with a school or employee ID" : reason}.</p>
    </ConsequentialActionDialog>
    <StepUpDialog open={stepUp !== null} requirement={stepUp ?? "verify"} reviewAfterVerification
      onOpenChange={(open) => { if (!open) { setStepUp(null); setEntryOpen(true); } }}
      onVerified={() => { setStepUp(null); setEntryOpen(true); }} />
  </>;
}

"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { isTurnstileConfigured, TurnstileWidget } from "@/features/auth/components/turnstile-widget";
import { accountErrorCode, accountErrorMessage } from "@/features/account/components/account-errors";
import { SecurityBackLink, StepUpDialog } from "@/features/account/security/security-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useAuthConfirmEmailChange,
  useAuthGetMfaStatus,
  useAuthRequestEmailChange,
  useAuthRequestEmailChangeSecurityChallenge,
} from "@/lib/api/generated/auth/auth";
import type { EmailChangeRequestResponse } from "@/lib/api/generated/model";

export function EmailChangePage() {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const mfa = useAuthGetMfaStatus({ query: { retry: false } });
  const challenge = useAuthRequestEmailChangeSecurityChallenge();
  const requestChange = useAuthRequestEmailChange();
  const confirmChange = useAuthConfirmEmailChange();
  const [currentChallengeId, setCurrentChallengeId] = useState<string | null>(null);
  const [currentCode, setCurrentCode] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newCode, setNewCode] = useState("");
  const [pending, setPending] = useState<EmailChangeRequestResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [setupRequired, setSetupRequired] = useState(false);
  const usesMfa = mfa.data?.data.enabled ?? false;
  const recent = mfa.data?.data.recent || verified;

  function resetTurnstile() {
    setToken(null);
    setResetKey((value) => value + 1);
  }

  function handleError(caught: unknown) {
    const code = accountErrorCode(caught);
    if (code === "recent_mfa_required") {
      setStepUpOpen(true);
      return;
    }
    if (code === "totp_step_up_required") setSetupRequired(true);
    setError(accountErrorMessage(caught, "The email change could not be completed. Please try again."));
  }

  async function requestCurrentProof() {
    setError(null);
    try {
      const response = await challenge.mutateAsync({ data: isTurnstileConfigured ? { turnstile_token: token } : {} });
      setCurrentChallengeId(response.data.challenge_id);
      resetTurnstile();
    } catch (caught) {
      handleError(caught);
      resetTurnstile();
    }
  }

  async function requestNewEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (usesMfa && !recent) {
      setStepUpOpen(true);
      return;
    }
    try {
      const response = await requestChange.mutateAsync({ data: {
        new_email: newEmail,
        ...(!usesMfa ? { current_email_challenge_id: currentChallengeId, current_email_code: currentCode } : {}),
        ...(isTurnstileConfigured ? { turnstile_token: token } : {}),
      } });
      setPending(response.data);
      setCurrentCode("");
      resetTurnstile();
    } catch (caught) {
      handleError(caught);
      resetTurnstile();
    }
  }

  async function confirmNewEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pending) return;
    setError(null);
    try {
      const response = await confirmChange.mutateAsync({ data: {
        request_id: pending.request_id,
        challenge_id: pending.challenge_id,
        code: newCode,
      } });
      if (!response.data.changed || !response.data.reauthentication_required) {
        setError("The email change could not be confirmed. Please try again.");
        return;
      }
      setNewCode("");
      queryClient.clear();
      window.location.replace("/login?email_changed=1");
    } catch (caught) {
      handleError(caught);
    }
  }

  const busy = challenge.isPending || requestChange.isPending || confirmChange.isPending;

  return (
    <section aria-labelledby="email-heading" className="max-w-2xl">
      <SecurityBackLink />
      <PageHeader
        title="Change sign-in email"
        headingId="email-heading"
        description={<>Current sign-in email: <span className="break-all font-semibold text-ink">{user.email}</span></>}
      />
      {mfa.isPending ? <RowsSkeleton label="Checking security requirements…" rows={2} framed /> : null}
      {mfa.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void mfa.refetch()}>Retry</Button>}>Security requirements could not be loaded.</Notice> : null}
      {mfa.isSuccess && !usesMfa && !currentChallengeId ? (
        <Panel as="div">
          <PanelHeader title="Verify your current email" description="First, request a code at your current sign-in email. You will verify the new email separately." />
          <PanelBody>
          <TurnstileWidget action="email_otp" onTokenChange={setToken} resetKey={resetKey} />
          <Button className="mt-4" disabled={busy || (isTurnstileConfigured && !token)} onClick={() => void requestCurrentProof()}>{challenge.isPending ? "Sending code…" : "Send current-email code"}</Button>
          </PanelBody>
        </Panel>
      ) : null}
      {mfa.isSuccess && !pending && (usesMfa || currentChallengeId) ? (
        <Panel as="div">
        <form onSubmit={requestNewEmail}>
          <PanelHeader title="Enter your new email" />
          <PanelBody className="space-y-5">
          {!usesMfa ? <div className="grid gap-2"><Label htmlFor="current-email-code">Code from current email</Label><Input id="current-email-code" autoComplete="one-time-code" inputMode="numeric" required value={currentCode} onChange={(event) => setCurrentCode(event.target.value)} /></div> : null}
          <div className="grid gap-2"><Label htmlFor="new-sign-in-email">New sign-in email</Label><Input id="new-sign-in-email" type="email" autoComplete="email" required value={newEmail} onChange={(event) => setNewEmail(event.target.value)} /></div>
          {usesMfa && !recent ? <p className="text-sm text-muted">Authenticator verification is required before the new email can be requested.</p> : null}
          <TurnstileWidget action="email_otp" onTokenChange={setToken} resetKey={resetKey} />
          <Button type="submit" disabled={busy || (isTurnstileConfigured && !token)}>{requestChange.isPending ? "Requesting change…" : usesMfa && !recent ? "Verify to continue" : "Send code to new email"}</Button>
          {!usesMfa ? <button type="button" onClick={() => { setCurrentChallengeId(null); setCurrentCode(""); setError(null); resetTurnstile(); }} className="block min-h-10 text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Request a new current-email code</button> : null}
          </PanelBody>
        </form>
        </Panel>
      ) : null}
      {mfa.isSuccess && pending ? (
        <Panel as="div">
        <form onSubmit={confirmNewEmail}>
          <PanelHeader
            title="Verify your new email"
            description={<>Enter the code sent to <span className="break-all font-semibold text-ink">{newEmail}</span>. Confirming this change will sign you out.</>}
          />
          <PanelBody className="space-y-5">
          <div className="grid gap-2"><Label htmlFor="new-email-code">Code from new email</Label><Input id="new-email-code" autoComplete="one-time-code" inputMode="numeric" required value={newCode} onChange={(event) => setNewCode(event.target.value)} /></div>
          <Button type="submit" disabled={busy}>{confirmChange.isPending ? "Changing email…" : "Change sign-in email"}</Button>
          <button type="button" onClick={() => { setPending(null); setNewCode(""); setError(null); }} className="block min-h-10 text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Start a new email request</button>
          </PanelBody>
        </form>
        </Panel>
      ) : null}
      {error ? <p role="alert" className="mt-5 text-sm text-danger">{error}</p> : null}
      {setupRequired ? <Link href="/portal/account/security/authenticator" className="mt-3 inline-flex min-h-10 items-center font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Manage authenticator</Link> : null}
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => setVerified(true)} />
    </section>
  );
}

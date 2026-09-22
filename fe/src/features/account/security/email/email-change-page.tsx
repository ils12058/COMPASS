"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
      <h1 id="email-heading" className="font-heading text-3xl font-bold text-ink">Change sign-in email</h1>
      <p className="mt-3 text-sm text-muted">Current sign-in email: <span className="break-all font-semibold text-ink">{user.email}</span></p>
      {mfa.isPending ? <p role="status" className="mt-7 text-sm text-muted">Checking security requirements…</p> : null}
      {mfa.isError ? <div role="alert" className="mt-7"><p className="text-sm text-danger">Security requirements could not be loaded.</p><Button variant="secondary" className="mt-3" onClick={() => void mfa.refetch()}>Retry</Button></div> : null}
      {mfa.isSuccess && !usesMfa && !currentChallengeId ? (
        <div className="mt-7 border-t border-border pt-6">
          <h2 className="font-heading text-xl font-semibold text-ink">Verify your current email</h2>
          <p className="mt-2 text-sm leading-6 text-muted">First, request a code at your current sign-in email. You will verify the new email separately.</p>
          <div className="mt-5"><TurnstileWidget action="email_otp" onTokenChange={setToken} resetKey={resetKey} /></div>
          <Button className="mt-4" disabled={busy || (isTurnstileConfigured && !token)} onClick={() => void requestCurrentProof()}>{challenge.isPending ? "Sending code…" : "Send current-email code"}</Button>
        </div>
      ) : null}
      {mfa.isSuccess && !pending && (usesMfa || currentChallengeId) ? (
        <form className="mt-7 space-y-5 border-t border-border pt-6" onSubmit={requestNewEmail}>
          <h2 className="font-heading text-xl font-semibold text-ink">Enter your new email</h2>
          {!usesMfa ? <div className="grid gap-2"><Label htmlFor="current-email-code">Code from current email</Label><Input id="current-email-code" autoComplete="one-time-code" inputMode="numeric" required value={currentCode} onChange={(event) => setCurrentCode(event.target.value)} /></div> : null}
          <div className="grid gap-2"><Label htmlFor="new-sign-in-email">New sign-in email</Label><Input id="new-sign-in-email" type="email" autoComplete="email" required value={newEmail} onChange={(event) => setNewEmail(event.target.value)} /></div>
          {usesMfa && !recent ? <p className="text-sm text-muted">Authenticator verification is required before the new email can be requested.</p> : null}
          <TurnstileWidget action="email_otp" onTokenChange={setToken} resetKey={resetKey} />
          <Button type="submit" disabled={busy || (isTurnstileConfigured && !token)}>{requestChange.isPending ? "Requesting change…" : usesMfa && !recent ? "Verify to continue" : "Send code to new email"}</Button>
          {!usesMfa ? <button type="button" onClick={() => { setCurrentChallengeId(null); setCurrentCode(""); setError(null); resetTurnstile(); }} className="block min-h-10 text-sm font-semibold text-brand hover:underline">Request a new current-email code</button> : null}
        </form>
      ) : null}
      {mfa.isSuccess && pending ? (
        <form className="mt-7 space-y-5 border-t border-border pt-6" onSubmit={confirmNewEmail}>
          <h2 className="font-heading text-xl font-semibold text-ink">Verify your new email</h2>
          <p className="text-sm leading-6 text-muted">Enter the code sent to <span className="break-all font-semibold text-ink">{newEmail}</span>. Confirming this change will sign you out.</p>
          <div className="grid gap-2"><Label htmlFor="new-email-code">Code from new email</Label><Input id="new-email-code" autoComplete="one-time-code" inputMode="numeric" required value={newCode} onChange={(event) => setNewCode(event.target.value)} /></div>
          <Button type="submit" disabled={busy}>{confirmChange.isPending ? "Changing email…" : "Change sign-in email"}</Button>
          <button type="button" onClick={() => { setPending(null); setNewCode(""); setError(null); }} className="block min-h-10 text-sm font-semibold text-brand hover:underline">Start a new email request</button>
        </form>
      ) : null}
      {error ? <p role="alert" className="mt-5 text-sm text-danger">{error}</p> : null}
      {setupRequired ? <Link href="/portal/account/security/authenticator" className="mt-3 inline-flex min-h-10 items-center font-semibold text-brand hover:underline">Manage authenticator</Link> : null}
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => setVerified(true)} />
    </section>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
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
import { useStepUpContinuation } from "@/features/account/security/step-up-continuation";
import { useOptionalActiveECounselingCall } from "@/features/ecounseling/runtime/active-call-context";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useAuthConfirmEmailChange,
  useAuthGetEmailChangeStatus,
  useAuthGetMfaStatus,
  useAuthRequestEmailChange,
  useAuthRequestEmailChangeSecurityChallenge,
} from "@/lib/api/generated/auth/auth";

export function EmailChangePage() {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const call = useOptionalActiveECounselingCall();
  const mfa = useAuthGetMfaStatus({ query: { retry: false } });
  const emailChangeStatus = useAuthGetEmailChangeStatus({
    query: { retry: false, refetchOnMount: "always", refetchOnWindowFocus: true },
  });
  const challenge = useAuthRequestEmailChangeSecurityChallenge();
  const requestChange = useAuthRequestEmailChange();
  const confirmChange = useAuthConfirmEmailChange();
  const continuation = useStepUpContinuation();
  const [currentChallengeId, setCurrentChallengeId] = useState<string | null>(null);
  const [currentCode, setCurrentCode] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newCode, setNewCode] = useState("");
  const [restartRequested, setRestartRequested] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [setupRequired, setSetupRequired] = useState(false);
  const usesMfa = mfa.data?.data.enabled ?? false;
  const recent = mfa.data?.data.recent ?? false;
  const serverRequest = emailChangeStatus.data?.data.request;
  const pending =
    !restartRequested && serverRequest?.status === "pending" && serverRequest.request_id && serverRequest.challenge_id
      ? {
          request_id: serverRequest.request_id,
          challenge_id: serverRequest.challenge_id,
          expires_at: serverRequest.expires_at ?? "",
          destination_email: serverRequest.destination_email ?? "",
        }
      : null;
  const formValuesRef = useRef({ currentChallengeId, currentCode, newEmail, newCode, token });
  useEffect(() => {
    formValuesRef.current = { currentChallengeId, currentCode, newEmail, newCode, token };
  }, [currentChallengeId, currentCode, newEmail, newCode, token]);

  function resetTurnstile() {
    setToken(null);
    setResetKey((value) => value + 1);
  }

  function handleTerminalError(caught: unknown) {
    const code = accountErrorCode(caught);
    if (code === "totp_step_up_required") setSetupRequired(true);
    setError(accountErrorMessage(caught, "The email change could not be completed. Please try again."));
  }

  async function requestCurrentProof() {
    setError(null);
    const response = await continuation.run(
      () => challenge.mutateAsync({ data: isTurnstileConfigured ? { turnstile_token: formValuesRef.current.token } : {} }),
      {
        onFailure: handleTerminalError,
      },
    );
    resetTurnstile();
    if (response) setCurrentChallengeId(response.data.challenge_id);
  }

  async function requestNewEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const destination = newEmail.trim();
    const currentChallenge = currentChallengeId;
    const response = await continuation.run(
      () => requestChange.mutateAsync({ data: {
        new_email: destination,
        ...(!usesMfa ? { current_email_challenge_id: currentChallenge, current_email_code: formValuesRef.current.currentCode } : {}),
        ...(isTurnstileConfigured ? { turnstile_token: formValuesRef.current.token } : {}),
      } }),
      {
        onFailure: handleTerminalError,
      },
    );
    resetTurnstile();
    if (!response) return;
    setRestartRequested(false);
    setCurrentChallengeId(null);
    setCurrentCode("");
    await emailChangeStatus.refetch();
  }

  async function confirmNewEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pending) return;
    setError(null);
    const target = { request_id: pending.request_id, challenge_id: pending.challenge_id };
    const response = await continuation.run(
      () => confirmChange.mutateAsync({ data: { ...target, code: formValuesRef.current.newCode } }),
      {
        onFailure: (caught) => {
          handleTerminalError(caught);
          void emailChangeStatus.refetch();
        },
      },
    );
    if (!response) return;
    if (!response.data.changed || !response.data.reauthentication_required) {
      setError("The email change could not be confirmed. Please try again.");
      return;
    }
    setNewCode("");
    // The change ended this sign-in, so an E-Counseling call ends with it before the reload.
    await call?.end();
    queryClient.clear();
    window.location.replace("/login?email_changed=1");
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
      {emailChangeStatus.isError ? (
        <Notice
          role="alert"
          tone="danger"
          className="mb-4"
          action={<Button variant="secondary" onClick={() => void emailChangeStatus.refetch()}>Retry</Button>}
        >
          Email verification status could not be loaded. Try again before requesting a new code.
        </Notice>
      ) : null}
      {emailChangeStatus.isSuccess && serverRequest && ["expired", "cancelled", "verification_unavailable"].includes(serverRequest.status) ? (
        <Notice role="status" tone="info" className="mb-4">
          This email change is no longer active. Start a new request to try again.
        </Notice>
      ) : null}
      {mfa.isPending ? <RowsSkeleton label="Checking security requirements…" rows={2} framed /> : null}
      {mfa.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void mfa.refetch()}>Retry</Button>}>Security requirements could not be loaded.</Notice> : null}
      {mfa.isSuccess && emailChangeStatus.isSuccess && !emailChangeStatus.isFetching && !pending && !usesMfa && !currentChallengeId ? (
        <Panel as="div">
          <PanelHeader title="Verify your current email" description="First, request a code at your current sign-in email. You will verify the new email separately." />
          <PanelBody>
          <TurnstileWidget action="email_otp" onTokenChange={setToken} resetKey={resetKey} />
          <Button className="mt-4" disabled={busy || (isTurnstileConfigured && !token)} onClick={() => void requestCurrentProof()}>{challenge.isPending ? "Sending code…" : "Send current-email code"}</Button>
          </PanelBody>
        </Panel>
      ) : null}
      {mfa.isSuccess && emailChangeStatus.isSuccess && !emailChangeStatus.isFetching && !pending && (usesMfa || currentChallengeId) ? (
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
      {mfa.isSuccess && emailChangeStatus.isSuccess && pending ? (
        <Panel as="div">
        <form onSubmit={confirmNewEmail}>
          <PanelHeader
            title="Verify your new email"
            description={<>Enter the code sent to <span className="break-all font-semibold text-ink">{pending.destination_email}</span>. Confirming this change will sign you out.</>}
          />
          <PanelBody className="space-y-5">
          <div className="grid gap-2"><Label htmlFor="new-email-code">Code from new email</Label><Input id="new-email-code" autoComplete="one-time-code" inputMode="numeric" required value={newCode} onChange={(event) => setNewCode(event.target.value)} /></div>
          <Button type="submit" disabled={busy}>{confirmChange.isPending ? "Verifying email…" : "Verify email"}</Button>
          <button type="button" onClick={() => { setRestartRequested(true); setCurrentChallengeId(null); setCurrentCode(""); setNewCode(""); setError(null); }} className="block min-h-10 text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Start a new email request</button>
          </PanelBody>
        </form>
        </Panel>
      ) : null}
      {error || continuation.notice ? <p role={error ? "alert" : "status"} className={`mt-5 text-sm ${error ? "text-danger" : "text-muted"}`}>{error ?? continuation.notice}</p> : null}
      {setupRequired ? <Link href="/portal/account/security/authenticator" className="mt-3 inline-flex min-h-10 items-center font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Manage authenticator</Link> : null}
      <StepUpDialog open={continuation.open} requirement={continuation.requirement} onOpenChange={continuation.setOpen} isContinuing={continuation.isContinuing} onVerified={continuation.continueAfterVerification} />
    </section>
  );
}

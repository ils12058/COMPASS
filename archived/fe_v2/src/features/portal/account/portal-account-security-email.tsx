"use client";

import { type FormEvent, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TurnstileWidget } from "@/features/auth/components/turnstile-widget";
import {
  useAuthConfirmEmailChange,
  useAuthRequestEmailChange,
  useAuthRequestEmailChangeSecurityChallenge,
} from "@/lib/api/generated/auth/auth";
import {
  SecurityMessage,
  SecuritySectionHeading,
  securityError,
} from "@/features/portal/account/portal-account-security-shared";

type EmailChangeStep = "idle" | "verify-current" | "verify-new";

export function PortalAccountSecurityEmail({
  currentEmail,
}: {
  currentEmail: string;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [step, setStep] = useState<EmailChangeStep>("idle");
  const [newEmail, setNewEmail] = useState("");
  const [currentEmailCode, setCurrentEmailCode] = useState("");
  const [newEmailCode, setNewEmailCode] = useState("");
  const [currentChallengeId, setCurrentChallengeId] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [newChallengeId, setNewChallengeId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);

  const requestCurrentChallenge = useAuthRequestEmailChangeSecurityChallenge();
  const requestEmailChange = useAuthRequestEmailChange();
  const confirmEmailChange = useAuthConfirmEmailChange();
  const hasTurnstile = Boolean(process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY?.trim());

  const handleTurnstileToken = useCallback((token: string | null) => {
    setTurnstileToken(token);
  }, []);

  async function beginEmailChange() {
    setError(null);
    setMessage(null);

    try {
      const response = await requestCurrentChallenge.mutateAsync({
        data: { turnstile_token: turnstileToken },
      });
      setCurrentChallengeId(response.data.challenge_id);
      setStep("verify-current");
      setTurnstileToken(null);
      setTurnstileResetKey((value) => value + 1);
      setMessage(`We sent a verification code to ${currentEmail}.`);
    } catch (caught) {
      setError(securityError(caught, "We couldn’t start the email change. Please try again."));
    }
  }

  async function requestNewEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const normalizedEmail = newEmail.trim().toLowerCase();
    if (!normalizedEmail || !normalizedEmail.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }
    if (!currentChallengeId || !currentEmailCode.trim()) {
      setError("Enter the code sent to your current email first.");
      return;
    }

    try {
      const response = await requestEmailChange.mutateAsync({
        data: {
          current_email_challenge_id: currentChallengeId,
          current_email_code: currentEmailCode.trim(),
          new_email: normalizedEmail,
          turnstile_token: turnstileToken,
        },
      });
      setRequestId(response.data.request_id);
      setNewChallengeId(response.data.challenge_id);
      setStep("verify-new");
      setCurrentEmailCode("");
      setTurnstileToken(null);
      setTurnstileResetKey((value) => value + 1);
      setMessage(`We sent a verification code to ${normalizedEmail}.`);
    } catch (caught) {
      setError(securityError(caught, "We couldn’t send the new email’s code. Please try again."));
    }
  }

  async function confirmNewEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    if (!newChallengeId || !requestId || !newEmailCode.trim()) {
      setError("Enter the code sent to your new email first.");
      return;
    }

    try {
      await confirmEmailChange.mutateAsync({
        data: {
          challenge_id: newChallengeId,
          code: newEmailCode.trim(),
          request_id: requestId,
        },
      });
      queryClient.clear();
      router.replace("/login?reason=email-changed");
      router.refresh();
    } catch (caught) {
      setError(securityError(caught, "We couldn’t confirm the email change. Please try again."));
    }
  }

  function resetEmailChange() {
    setStep("idle");
    setNewEmail("");
    setCurrentEmailCode("");
    setNewEmailCode("");
    setCurrentChallengeId(null);
    setRequestId(null);
    setNewChallengeId(null);
    setError(null);
    setMessage(null);
    setTurnstileToken(null);
    setTurnstileResetKey((value) => value + 1);
  }

  return (
    <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
      <SecuritySectionHeading
        icon={Mail}
        title="Sign-in email"
        description="Changing this address uses verification on both the current and new mailboxes, then signs you out so you can sign in again with the new address."
      />
      <div className="mt-6 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground">Current address</p>
        <p className="mt-2 break-words font-semibold">{currentEmail}</p>
      </div>

      <div className="mt-6 space-y-5">
        <TurnstileWidget
          action="email_otp"
          onToken={handleTurnstileToken}
          resetKey={turnstileResetKey}
        />

        {step === "idle" ? (
          <div className="space-y-4">
            <p className="text-sm leading-6 text-muted-foreground">
              We’ll first send a code to your current address. Have access to both mailboxes before you begin.
            </p>
            <Button
              type="button"
              variant="outline"
              disabled={requestCurrentChallenge.isPending || (hasTurnstile && !turnstileToken)}
              onClick={() => void beginEmailChange()}
            >
              <Mail aria-hidden="true" />
              {requestCurrentChallenge.isPending ? "Sending code…" : "Change sign-in email"}
            </Button>
          </div>
        ) : null}

        {step === "verify-current" ? (
          <form className="space-y-5" onSubmit={(event) => void requestNewEmail(event)}>
            <div className="space-y-2">
              <Label htmlFor="current-email-code">Code from your current email</Label>
              <Input
                id="current-email-code"
                value={currentEmailCode}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={12}
                placeholder="Enter the code"
                onChange={(event) => setCurrentEmailCode(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-sign-in-email">New sign-in email</Label>
              <Input
                id="new-sign-in-email"
                type="email"
                value={newEmail}
                autoComplete="email"
                placeholder="name@ucn.edu.ph"
                onChange={(event) => setNewEmail(event.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={requestEmailChange.isPending}>
                <Mail aria-hidden="true" />
                {requestEmailChange.isPending ? "Checking code…" : "Send new email code"}
              </Button>
              <Button type="button" variant="ghost" onClick={resetEmailChange}>Cancel</Button>
            </div>
          </form>
        ) : null}

        {step === "verify-new" ? (
          <form className="space-y-5" onSubmit={(event) => void confirmNewEmail(event)}>
            <div className="rounded-2xl border border-[var(--compass-support)]/30 bg-[var(--compass-support-soft)] p-4 text-sm leading-6 text-[var(--compass-support-strong)]">
              Enter the code sent to <strong>{newEmail}</strong> to finish the change.
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-email-code">Code from your new email</Label>
              <Input
                id="new-email-code"
                value={newEmailCode}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={12}
                placeholder="Enter the code"
                onChange={(event) => setNewEmailCode(event.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={confirmEmailChange.isPending}>
                <Check aria-hidden="true" />
                {confirmEmailChange.isPending ? "Confirming…" : "Confirm email change"}
              </Button>
              <Button type="button" variant="ghost" onClick={resetEmailChange}>Cancel</Button>
            </div>
          </form>
        ) : null}

        <SecurityMessage error={error} message={message} />
      </div>
    </section>
  );
}

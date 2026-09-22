"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FormError } from "@/features/auth/components/auth-states";
import { PasswordInput } from "@/features/auth/components/password-input";
import {
  isTurnstileConfigured,
  TurnstileWidget,
} from "@/features/auth/components/turnstile-widget";
import { authErrorMessage, passwordPolicyMessages } from "@/features/auth/utils/errors";
import {
  useAuthConfirmPasswordAccess,
  useAuthRequestPasswordAccess,
} from "@/lib/api/generated/auth/auth";

type ConfirmState = {
  challengeId: string;
  expiresAt: string;
  message: string;
};

export function PasswordAccess() {
  const [email, setEmail] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [complete, setComplete] = useState(false);
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [policyMessages, setPolicyMessages] = useState<string[]>([]);
  const requestAccess = useAuthRequestPasswordAccess();
  const confirmAccess = useAuthConfirmPasswordAccess();

  async function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    try {
      const response = await requestAccess.mutateAsync({
        data: {
          email,
          ...(isTurnstileConfigured ? { turnstile_token: turnstileToken } : {}),
        },
      });
      setConfirmState({
        challengeId: response.data.challenge_id,
        expiresAt: response.data.expires_at,
        message: response.data.message,
      });
    } catch (caught) {
      setError(authErrorMessage(caught, "The password access request could not be completed."));
    } finally {
      if (isTurnstileConfigured) {
        setTurnstileToken(null);
        setTurnstileResetKey((current) => current + 1);
      }
    }
  }

  async function updatePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPolicyMessages([]);

    if (!confirmState) return;
    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
      return;
    }

    try {
      const response = await confirmAccess.mutateAsync({
        data: {
          challenge_id: confirmState.challengeId,
          code,
          new_password: newPassword,
        },
      });

      if (!response.data.password_set) {
        setError("The password could not be updated.");
        return;
      }

      setCode("");
      setNewPassword("");
      setConfirmPassword("");
      setComplete(true);
    } catch (caught) {
      const issues = passwordPolicyMessages(caught);
      setPolicyMessages(issues);
      setError(
        issues.length > 0
          ? "The new password does not meet the password policy."
          : authErrorMessage(caught, "The password could not be updated. Please try again."),
      );
    }
  }

  function restartRequest() {
    setConfirmState(null);
    setCode("");
    setNewPassword("");
    setConfirmPassword("");
    setError(null);
    setPolicyMessages([]);
  }

  if (complete) {
    return (
      <section>
        <h1 className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">Password updated</h1>
        <p className="mt-3 text-sm leading-6 text-muted">You can now sign in to COMPASS.</p>
        <Link
          href="/login"
          className="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-md bg-brand px-4 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Return to sign in
        </Link>
      </section>
    );
  }

  if (!confirmState) {
    return (
      <section aria-labelledby="password-heading">
        <h1 id="password-heading" className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Set up or reset your password
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">Enter your COMPASS sign-in email.</p>

        <form className="mt-8 space-y-5" onSubmit={requestCode}>
          <div className="grid gap-2">
            <Label htmlFor="password-email">Email</Label>
            <Input
              id="password-email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-describedby={error ? "password-request-error" : undefined}
            />
          </div>
          <TurnstileWidget action="email_otp" onTokenChange={setTurnstileToken} resetKey={turnstileResetKey} />
          <FormError id="password-request-error" message={error} />
          <Button
            type="submit"
            className="w-full"
            disabled={requestAccess.isPending || (isTurnstileConfigured && !turnstileToken)}
          >
            {requestAccess.isPending ? "Sending code…" : "Continue"}
          </Button>
        </form>

        <Link className="mt-5 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline" href="/login">
          Return to sign in
        </Link>
      </section>
    );
  }

  return (
    <section aria-labelledby="confirm-password-heading">
      <h1 id="confirm-password-heading" className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">
        Check your email
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">{confirmState.message}</p>

      <form className="mt-8 space-y-5" onSubmit={updatePassword}>
        <div className="grid gap-2">
          <Label htmlFor="security-code">Security code</Label>
          <Input
            id="security-code"
            name="code"
            autoComplete="one-time-code"
            inputMode="numeric"
            required
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="new-password">New password</Label>
          <PasswordInput
            id="new-password"
            name="new-password"
            autoComplete="new-password"
            required
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="confirm-new-password">Confirm new password</Label>
          <PasswordInput
            id="confirm-new-password"
            name="confirm-new-password"
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            aria-describedby={error ? "password-confirm-error" : undefined}
          />
        </div>

        <FormError id="password-confirm-error" message={error} />
        {policyMessages.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5 text-sm text-danger">
            {policyMessages.map((message) => <li key={message}>{message}</li>)}
          </ul>
        ) : null}
        <Button type="submit" className="w-full" disabled={confirmAccess.isPending}>
          {confirmAccess.isPending ? "Updating password…" : "Update password"}
        </Button>
      </form>

      <button
        type="button"
        onClick={restartRequest}
        className="mt-5 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Request a new code
      </button>
    </section>
  );
}

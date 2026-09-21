"use client";

import Link from "next/link";
import { useCallback, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { PasswordInput } from "@/features/auth/components/password-input";
import { TurnstileWidget } from "@/features/auth/components/turnstile-widget";
import {
  friendlyAuthError,
  getApiErrorCode,
  getPasswordPolicyMessages,
} from "@/features/auth/utils/errors";
import {
  useAuthConfirmPasswordAccess,
  useAuthRequestPasswordAccess,
} from "@/lib/api/generated/auth/auth";

type PasswordStage = "request" | "confirm" | "complete";

export function PasswordAccess() {
  const requestAccess = useAuthRequestPasswordAccess();
  const confirmAccess = useAuthConfirmPasswordAccess();

  const [stage, setStage] = useState<PasswordStage>("request");
  const [email, setEmail] = useState("");
  const [challengeId, setChallengeId] = useState("");
  const [challengeExpiresAt, setChallengeExpiresAt] = useState<string | null>(null);
  const [securityCode, setSecurityCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [policyMessages, setPolicyMessages] = useState<string[]>([]);

  const onTurnstileToken = useCallback((token: string | null) => {
    setTurnstileToken(token);
  }, []);

  function resetConfirmation() {
    setSecurityCode("");
    setNewPassword("");
    setConfirmPassword("");
    setChallengeId("");
    setChallengeExpiresAt(null);
    setMessage(null);
    setPolicyMessages([]);
  }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    try {
      const response = await requestAccess.mutateAsync({
        data: {
          email: email.trim(),
          turnstile_token: turnstileToken,
        },
      });

      setChallengeId(response.data.challenge_id);
      setChallengeExpiresAt(response.data.expires_at);
      setMessage(response.data.message);
      setStage("confirm");
    } catch (caught) {
      setError(
        getApiErrorCode(caught) === "security_verification_failed"
          ? "Security verification could not be completed. Please try again."
          : friendlyAuthError(caught, "The password request could not be completed."),
      );
    } finally {
      setTurnstileToken(null);
      setTurnstileResetKey((value) => value + 1);
    }
  }

  async function submitConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPolicyMessages([]);

    if (newPassword !== confirmPassword) {
      setError("The password confirmation does not match.");
      return;
    }

    try {
      await confirmAccess.mutateAsync({
        data: {
          challenge_id: challengeId,
          code: securityCode.trim(),
          new_password: newPassword,
        },
      });

      resetConfirmation();
      setStage("complete");
    } catch (caught) {
      setSecurityCode("");
      setNewPassword("");
      setConfirmPassword("");

      if (getApiErrorCode(caught) === "password_policy_failed") {
        setPolicyMessages(getPasswordPolicyMessages(caught));
        setError("Choose a different password and try again.");
      } else {
        setError(
          friendlyAuthError(
            caught,
            "The security code or password could not be accepted. Please try again.",
          ),
        );
      }
    }
  }

  if (stage === "complete") {
    return (
      <AuthShell
        title="Password updated"
        description="Your new password is ready. Sign in to continue."
      >
        <div className="space-y-5">
          <div className="rounded-xl border border-[color-mix(in_srgb,var(--compass-success)_25%,transparent)] bg-[color-mix(in_srgb,var(--compass-success)_8%,transparent)] p-4 text-sm leading-6 text-[var(--compass-success)]">
            Your password has been updated. For your security, you’ll need to sign in again.
          </div>
          <Button asChild className="w-full" size="lg">
            <Link href="/login">Sign in to COMPASS</Link>
          </Button>
        </div>
      </AuthShell>
    );
  }

  if (stage === "confirm") {
    const expiresAt = challengeExpiresAt ? new Date(challengeExpiresAt) : null;
    const expiresLabel = expiresAt && !Number.isNaN(expiresAt.valueOf())
      ? expiresAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
      : null;

    return (
      <AuthShell
        title="Choose a new password"
        description="Enter the code we sent to your email, then choose a new password."
      >
        <form className="space-y-5" onSubmit={submitConfirmation}>
          {message ? (
            <p role="status" className="rounded-xl bg-[var(--compass-surface-subtle)] p-4 text-sm leading-6 text-muted-foreground">
              {message}{expiresLabel ? ` The code expires at ${expiresLabel}.` : ""}
            </p>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="password-security-code">Security code</Label>
            <Input
              id="password-security-code"
              value={securityCode}
              onChange={(event) => setSecurityCode(event.target.value.replace(/\s/g, ""))}
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="Enter the code from your email"
              required
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-password">New password</Label>
            <PasswordInput
              id="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              aria-describedby="password-guidance"
              required
            />
            <p id="password-guidance" className="text-xs leading-5 text-muted-foreground">
              Choose a long, unique password that you have not used elsewhere. If it does not meet
              the account requirements, we will show the specific guidance here.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm-new-password">Confirm new password</Label>
            <PasswordInput
              id="confirm-new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              aria-invalid={confirmPassword.length > 0 && newPassword !== confirmPassword}
              required
            />
            {confirmPassword.length > 0 && newPassword !== confirmPassword ? (
              <p className="text-xs text-destructive">Passwords do not match yet.</p>
            ) : null}
          </div>

          {policyMessages.length ? (
            <div
              className="rounded-xl border border-destructive/25 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              <p className="font-semibold">Password requirements</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {policyMessages.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {error ? (
            <p role="alert" aria-live="polite" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}

          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="submit"
              size="lg"
              className="flex-1"
              disabled={
                confirmAccess.isPending ||
                !securityCode.trim() ||
                !newPassword ||
                !confirmPassword
              }
            >
              {confirmAccess.isPending ? "Updating…" : "Set password"}
            </Button>
            <Button
              type="button"
              size="lg"
              variant="ghost"
              onClick={() => {
                resetConfirmation();
                setError(null);
                setStage("request");
              }}
              disabled={confirmAccess.isPending}
            >
              Start over
            </Button>
          </div>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Set or reset your password"
      description="Enter your UCN email to request a one-time security code."
    >
      <form className="space-y-5" onSubmit={submitRequest}>
        <div className="space-y-2">
          <Label htmlFor="password-email">UCN email</Label>
          <Input
            id="password-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            placeholder="you@ucn.edu.ph"
            required
            autoFocus
          />
        </div>

        <TurnstileWidget
          action="email_otp"
          onToken={onTurnstileToken}
          resetKey={turnstileResetKey}
        />

        {error ? (
          <p role="alert" aria-live="polite" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <Button type="submit" size="lg" className="w-full" disabled={requestAccess.isPending}>
          {requestAccess.isPending ? "Sending…" : "Continue"}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Remember your password?{" "}
          <Link className="font-semibold text-[var(--compass-brand-maroon)]" href="/login">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

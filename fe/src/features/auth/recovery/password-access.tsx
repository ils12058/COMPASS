"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/features/auth/components/auth-shell";
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

  async function submitRequest(event: React.FormEvent<HTMLFormElement>) {
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

  async function submitConfirmation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPolicyMessages([]);

    if (newPassword !== confirmPassword) {
      setError("The password confirmation does not match.");
      return;
    }

    const code = securityCode.trim();

    try {
      await confirmAccess.mutateAsync({
        data: {
          challenge_id: challengeId,
          code,
          new_password: newPassword,
        },
      });

      setSecurityCode("");
      setNewPassword("");
      setConfirmPassword("");
      setChallengeId("");
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
        description="Your password is ready. Sign in to create a new COMPASS session."
      >
        <div className="space-y-5">
          <p className="text-sm text-muted-foreground">
            Password setup or recovery is complete. For your security, this step does not sign
            you in automatically.
          </p>
          <Button onClick={() => window.location.assign("/login")}>Sign in to COMPASS</Button>
        </div>
      </AuthShell>
    );
  }

  if (stage === "confirm") {
    return (
      <AuthShell
        title="Enter your security code"
        description="Use the code sent for this password request and choose your new password."
      >
        <form className="space-y-5" onSubmit={submitConfirmation}>
          {message ? (
            <p role="status" className="rounded-lg bg-muted p-3 text-sm text-muted-foreground">
              {message}
            </p>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="password-security-code">Security code</Label>
            <Input
              id="password-security-code"
              value={securityCode}
              onChange={(event) => setSecurityCode(event.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-password">New password</Label>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm-new-password">Confirm new password</Label>
            <Input
              id="confirm-new-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              required
            />
          </div>

          {policyMessages.length ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-destructive">
              {policyMessages.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}

          {error ? (
            <p role="alert" aria-live="polite" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={confirmAccess.isPending}>
              {confirmAccess.isPending ? "Updating…" : "Set password"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setSecurityCode("");
                setNewPassword("");
                setConfirmPassword("");
                setChallengeId("");
                setMessage(null);
                setStage("request");
              }}
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
      description="Enter your university email to request a security code."
    >
      <form className="space-y-5" onSubmit={submitRequest}>
        <div className="space-y-2">
          <Label htmlFor="password-email">Email</Label>
          <Input
            id="password-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
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

        <Button type="submit" className="w-full" disabled={requestAccess.isPending}>
          {requestAccess.isPending ? "Sending…" : "Continue"}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Remember your password?{" "}
          <Link className="font-semibold" href="/login">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

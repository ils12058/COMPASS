"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TurnstileWidget } from "@/features/auth/components/turnstile-widget";

export type LoginCredentials = {
  email: string;
  password: string;
  trustBrowser: boolean;
  turnstileToken: string | null;
};

export function LoginForm({
  busy,
  error,
  notice,
  onSubmit,
}: {
  busy: boolean;
  error: string | null;
  notice: string | null;
  onSubmit: (credentials: LoginCredentials) => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [trustBrowser, setTrustBrowser] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);

  const onTurnstileToken = useCallback((token: string | null) => {
    setTurnstileToken(token);
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      await onSubmit({
        email: email.trim(),
        password,
        trustBrowser,
        turnstileToken,
      });
    } finally {
      setPassword("");
      setTurnstileToken(null);
      setTurnstileResetKey((value) => value + 1);
    }
  }

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="space-y-2">
        <Label htmlFor="login-email">Email</Label>
        <Input
          id="login-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="username"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="login-password">Password</Label>
        <Input
          id="login-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </div>

      <label className="flex items-start gap-3 text-sm">
        <input
          className="mt-1 size-4"
          type="checkbox"
          checked={trustBrowser}
          onChange={(event) => setTrustBrowser(event.target.checked)}
        />
        <span>
          <span className="font-semibold">Trust this browser after verification</span>
          <span className="mt-0.5 block text-muted-foreground">
            This can skip two-step verification on future sign-ins after your password is
            verified.
          </span>
        </span>
      </label>

      <TurnstileWidget
        action="login"
        onToken={onTurnstileToken}
        resetKey={turnstileResetKey}
      />

      {notice ? (
        <p role="status" aria-live="polite" className="text-sm text-[var(--compass-success)]">
          {notice}
        </p>
      ) : null}

      {error ? (
        <p role="alert" aria-live="polite" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Button type="submit" className="w-full" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Need to set or reset your password?{" "}
        <Link className="font-semibold" href="/password">
          Set or reset password
        </Link>
      </p>
    </form>
  );
}

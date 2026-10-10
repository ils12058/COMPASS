"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/features/auth/components/password-input";
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
        <Label htmlFor="login-email">UCN email</Label>
        <Input
          id="login-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="username"
          placeholder="you@ucn.edu.ph"
          required
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <Label htmlFor="login-password">Password</Label>
          <Link
            href="/password"
            className="text-xs font-semibold text-[var(--compass-brand-maroon)]"
          >
            Set or reset your password
          </Link>
        </div>
        <PasswordInput
          id="login-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </div>

      <label className="flex items-start gap-3 text-sm leading-6">
        <Checkbox
          checked={trustBrowser}
          onCheckedChange={(checked) => setTrustBrowser(checked === true)}
          className="mt-1"
        />
        <span>
          <span className="font-semibold">Remember this browser</span>
          <span className="mt-0.5 block text-muted-foreground">
            Only use this on a private device. It may reduce future verification steps.
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

      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>

    </form>
  );
}

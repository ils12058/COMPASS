"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FormError } from "@/features/auth/components/auth-states";
import { isTurnstileConfigured, TurnstileWidget } from "@/features/auth/components/turnstile-widget";
import { authErrorMessage } from "@/features/auth/utils/errors";
import { useAuthRequestPasswordLink } from "@/lib/api/generated/auth/auth";

export function PasswordAccess() {
  const [email, setEmail] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const request = useAuthRequestPasswordLink();

  async function sendLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (request.isPending) return;
    setError(null);
    try {
      const response = await request.mutateAsync({ data: { email,
        ...(isTurnstileConfigured ? { turnstile_token: turnstileToken } : {}),
      } });
      setMessage(response.data.message);
    } catch (caught) { setError(authErrorMessage(caught, "Couldn't request a password link. Try again.")); }
    finally {
      if (isTurnstileConfigured) { setTurnstileToken(null); setTurnstileResetKey((current) => current + 1); }
    }
  }

  return <section aria-labelledby="password-heading">
    <h1 id="password-heading" className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">
      {message ? "Check your email" : "Set up or reset your password"}
    </h1>
    {message ? <>
      <p role="status" className="mt-3 text-sm leading-6 text-muted">{message}</p>
      <p className="mt-3 text-sm leading-6 text-muted">Open the link in your email to choose a new password. If you no longer have access to that email, ask the ITSO for help.</p>
      <Button className="mt-5" variant="secondary" onClick={() => { setMessage(null); setError(null); }}>Request another link</Button>
    </> : <>
      <p className="mt-3 text-sm leading-6 text-muted">Enter your COMPASS sign-in email.</p>
      <form className="mt-8 space-y-5" onSubmit={sendLink} aria-busy={request.isPending}>
        <div className="grid gap-2">
          <Label htmlFor="password-email">Email</Label>
          <Input id="password-email" name="email" type="email" autoComplete="email" required value={email}
            onChange={(event) => setEmail(event.target.value)} aria-describedby={error ? "password-request-error" : undefined} />
        </div>
        <TurnstileWidget action="email_otp" onTokenChange={setTurnstileToken} resetKey={turnstileResetKey} />
        <FormError id="password-request-error" message={error} />
        <Button type="submit" className="w-full" disabled={request.isPending || (isTurnstileConfigured && !turnstileToken)}>
          {request.isPending ? "Requesting link…" : "Send password link"}
        </Button>
      </form>
    </>}
    <Link className="mt-5 inline-flex min-h-11 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href="/login">Return to sign in</Link>
  </section>;
}

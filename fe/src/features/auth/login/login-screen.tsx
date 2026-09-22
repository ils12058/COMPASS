"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthFlow } from "@/features/auth/components/auth-flow-context";
import { AuthFailure, AuthSessionLoading, FormError } from "@/features/auth/components/auth-states";
import { PasswordInput } from "@/features/auth/components/password-input";
import {
  isTurnstileConfigured,
  TurnstileWidget,
} from "@/features/auth/components/turnstile-widget";
import { authErrorMessage } from "@/features/auth/utils/errors";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  getAuthGetSessionQueryKey,
  useAuthGetSession,
  useAuthLogin,
} from "@/lib/api/generated/auth/auth";

function LoginForm({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const flow = useAuthFlow();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [trustBrowser, setTrustBrowser] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const login = useAuthLogin();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    try {
      const response = await login.mutateAsync({
        data: {
          email,
          password,
          trust_browser: trustBrowser,
          ...(isTurnstileConfigured ? { turnstile_token: turnstileToken } : {}),
        },
      });

      if (response.data.authenticated) {
        flow.clearFlow();
        queryClient.removeQueries({ queryKey: getAuthGetSessionQueryKey() });
        router.replace(nextPath);
        return;
      }

      if (response.data.mfa_required && response.data.mfa_methods.length > 0) {
        flow.beginMfa(
          response.data.mfa_methods,
          response.data.challenge_expires_at ?? null,
          nextPath,
        );
        router.replace("/login/verify");
        return;
      }

      setError("Sign in could not be completed. Please try again.");
    } catch (caught) {
      if (
        caught instanceof CompassApiError &&
        caught.status === 403 &&
        readApiErrorCode(caught.body) === "mfa_setup_required"
      ) {
        flow.beginMandatorySetup(nextPath);
        router.replace("/login/setup-authenticator");
        return;
      }

      setError(authErrorMessage(caught, "Sign in could not be completed. Please try again."));
    } finally {
      if (isTurnstileConfigured) {
        setTurnstileToken(null);
        setTurnstileResetKey((current) => current + 1);
      }
    }
  }

  return (
    <section aria-labelledby="login-heading">
      <h1 id="login-heading" className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">
        Sign in to COMPASS
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        Use your University of Camarines Norte COMPASS account.
      </p>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <div className="grid gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby={error ? "login-error" : undefined}
          />
        </div>

        <label className="flex items-start gap-3 text-sm text-ink">
          <input
            type="checkbox"
            checked={trustBrowser}
            onChange={(event) => setTrustBrowser(event.target.checked)}
            className="mt-1 size-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          />
          <span>
            <span className="font-semibold">Trust this browser for future sign-ins</span>
            <span className="mt-1 block text-xs leading-5 text-muted">Use this only on a device you control.</span>
          </span>
        </label>

        <TurnstileWidget action="login" onTokenChange={setTurnstileToken} resetKey={turnstileResetKey} />
        <FormError id="login-error" message={error} />

        <Button
          type="submit"
          className="w-full"
          disabled={login.isPending || (isTurnstileConfigured && !turnstileToken)}
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <Link
        href="/password"
        className="mt-6 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Forgot your password or need to set one up?
      </Link>
    </section>
  );
}

export function LoginScreen({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const session = useAuthGetSession({ query: { retry: false } });

  useEffect(() => {
    if (session.isSuccess) router.replace(nextPath);
  }, [nextPath, router, session.isSuccess]);

  if (session.isPending || session.isSuccess) return <AuthSessionLoading />;

  const confirmedSignedOut = session.error instanceof CompassApiError && session.error.status === 401;
  if (confirmedSignedOut) return <LoginForm nextPath={nextPath} />;

  return (
    <AuthFailure
      message="We couldn't verify whether you are already signed in."
      onRetry={() => void session.refetch()}
    />
  );
}

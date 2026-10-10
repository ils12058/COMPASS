"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthFlow } from "@/features/auth/components/auth-flow-context";
import { FormError } from "@/features/auth/components/auth-states";
import { authErrorMessage } from "@/features/auth/utils/errors";
import {
  getAuthGetSessionQueryKey,
  useAuthVerifyLoginMfa,
} from "@/lib/api/generated/auth/auth";
import { LoginMFAMethod } from "@/lib/api/generated/model";

export function MfaVerification() {
  const flow = useAuthFlow();
  const router = useRouter();
  const queryClient = useQueryClient();
  const preferredMethod = flow.mfaMethods.includes(LoginMFAMethod.totp)
    ? LoginMFAMethod.totp
    : flow.mfaMethods[0];
  const [method, setMethod] = useState(preferredMethod);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const verify = useAuthVerifyLoginMfa();

  if (!method || !flow.mfaMethods.includes(method)) {
    return (
      <section>
        <h1 className="font-heading text-3xl font-bold text-ink">Restart sign in</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          The sign-in verification details are no longer available.
        </p>
        <Link className="mt-6 inline-flex min-h-10 items-center font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href="/login">
          Return to sign in
        </Link>
      </section>
    );
  }

  const usingRecovery = method === LoginMFAMethod.recovery;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    try {
      const response = await verify.mutateAsync({ data: { code, method } });
      if (!response.data.authenticated) {
        setError("Verification did not create a session. Restart sign in.");
        return;
      }

      const destination = flow.nextPath;
      flow.clearFlow();
      queryClient.removeQueries({ queryKey: getAuthGetSessionQueryKey() });
      router.replace(destination);
    } catch (caught) {
      setError(authErrorMessage(caught, "Verification could not be completed. Please try again."));
    }
  }

  function switchMethod(nextMethod: LoginMFAMethod) {
    setMethod(nextMethod);
    setCode("");
    setError(null);
  }

  return (
    <section aria-labelledby="verify-heading">
      <h1 id="verify-heading" className="font-heading text-3xl font-bold tracking-tight text-ink sm:text-4xl">
        {usingRecovery ? "Use a recovery code" : "Verify your identity"}
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        {usingRecovery
          ? "Enter one of your saved recovery codes."
          : "Enter the 6-digit code from your authenticator app."}
      </p>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <div className="grid gap-2">
          <Label htmlFor="mfa-code">{usingRecovery ? "Recovery code" : "Authenticator code"}</Label>
          <Input
            id="mfa-code"
            name="code"
            autoComplete={usingRecovery ? "off" : "one-time-code"}
            inputMode={usingRecovery ? "text" : "numeric"}
            maxLength={usingRecovery ? undefined : 6}
            required
            value={code}
            onChange={(event) => setCode(event.target.value)}
            aria-describedby={error ? "mfa-error" : undefined}
          />
        </div>
        <FormError id="mfa-error" message={error} />
        <Button type="submit" className="w-full" disabled={verify.isPending}>
          {verify.isPending ? "Verifying…" : "Verify"}
        </Button>
      </form>

      {flow.mfaMethods.includes(LoginMFAMethod.recovery) && !usingRecovery ? (
        <button
          type="button"
          onClick={() => switchMethod(LoginMFAMethod.recovery)}
          className="mt-5 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Use a recovery code instead
        </button>
      ) : null}

      {flow.mfaMethods.includes(LoginMFAMethod.totp) && usingRecovery ? (
        <button
          type="button"
          onClick={() => switchMethod(LoginMFAMethod.totp)}
          className="mt-5 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Use an authenticator code instead
        </button>
      ) : null}
    </section>
  );
}

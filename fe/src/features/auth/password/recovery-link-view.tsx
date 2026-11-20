import Link from "next/link";
import type { FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { AuthSessionLoading, FormError } from "@/features/auth/components/auth-states";
import { PasswordInput } from "@/features/auth/components/password-input";
import type { RecoveryLinkVerifyResponse } from "@/lib/api/generated/model";

export const unavailableLinkMessage = "This link is unavailable. Ask the ITSO for a new link.";

export type RecoveryPageState =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | { kind: "error"; message: string }
  | { kind: "success"; emailChange: boolean }
  | { kind: "valid"; details: RecoveryLinkVerifyResponse };

export function RecoveryLinkView({ state, newPassword = "", confirmPassword = "", error = null,
  policyMessages = [], pending = false, onPasswordChange, onConfirmChange, onSubmit, onRetry,
}: {
  state: RecoveryPageState;
  newPassword?: string;
  confirmPassword?: string;
  error?: string | null;
  policyMessages?: string[];
  pending?: boolean;
  onPasswordChange?: (value: string) => void;
  onConfirmChange?: (value: string) => void;
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
  onRetry?: () => void;
}) {
  if (state.kind === "loading") return <AuthSessionLoading label="Checking your recovery link…" />;
  if (state.kind === "unavailable" || state.kind === "error") {
    return <section aria-labelledby="recovery-heading">
      <h1 id="recovery-heading" className="font-heading text-3xl font-bold text-ink">Couldn&apos;t open recovery</h1>
      <p role="alert" className="mt-3 text-sm leading-6 text-muted">{state.kind === "unavailable" ? unavailableLinkMessage : state.message}</p>
      {state.kind === "error" ? <Button className="mt-5" variant="secondary" onClick={onRetry}>Retry</Button> : null}
    </section>;
  }
  if (state.kind === "success") {
    return <section aria-labelledby="recovery-heading">
      <h1 id="recovery-heading" className="font-heading text-3xl font-bold text-ink">Password updated</h1>
      <p role="status" className="mt-3 text-sm leading-6 text-muted">
        {state.emailChange ? "Your sign-in email was changed and your password was updated." : "Your password was updated."} All existing sign-ins were ended.
      </p>
      <p className="mt-3 text-sm leading-6 text-muted">Sign in with your new password. If you have an authenticator, you still need it.</p>
      <Link href="/login" className={buttonVariants({ className: "mt-6 w-full" })}>Return to sign in</Link>
    </section>;
  }
  return <section aria-labelledby="recovery-heading">
    <h1 id="recovery-heading" className="font-heading text-3xl font-bold text-ink">Choose a new password</h1>
    <p className="mt-3 break-words text-sm leading-6 text-muted">
      {state.details.email_change ? "Your sign-in email will change to " : "Account email: "}
      <span className="font-semibold text-ink">{state.details.masked_email}</span>.
    </p>
    <p className="mt-3 text-sm leading-6 text-muted">You will be signed out everywhere. An existing authenticator stays in place. If you lost it, ask the ITSO for help.</p>
    <form className="mt-6 space-y-5" onSubmit={onSubmit} aria-busy={pending}>
      <div className="grid gap-2">
        <Label htmlFor="recovery-password">New password</Label>
        <PasswordInput id="recovery-password" autoComplete="new-password" required value={newPassword}
          onChange={(event) => onPasswordChange?.(event.target.value)} disabled={pending}
          aria-invalid={policyMessages.length > 0} aria-describedby={policyMessages.length ? "recovery-policy" : undefined} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="recovery-confirm">Confirm new password</Label>
        <PasswordInput id="recovery-confirm" autoComplete="new-password" required value={confirmPassword}
          onChange={(event) => onConfirmChange?.(event.target.value)} disabled={pending}
          aria-describedby={error ? "recovery-error" : undefined} aria-invalid={!!error} />
      </div>
      <FormError id="recovery-error" message={error} />
      {policyMessages.length > 0 ? <ul id="recovery-policy" className="list-disc space-y-1 pl-5 text-sm text-danger">
        {policyMessages.map((message) => <li key={message}>{message}</li>)}
      </ul> : null}
      <Button type="submit" className="w-full" disabled={pending}>{pending ? "Updating password…" : "Update password"}</Button>
    </form>
  </section>;
}

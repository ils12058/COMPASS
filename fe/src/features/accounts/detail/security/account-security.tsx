"use client";

import Link from "next/link";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  ManagedActionFeedback,
  useInvalidateManagedAccount,
  useManagedAction,
} from "@/features/accounts/components/account-action";
import { useManagedAccount } from "@/features/accounts/detail/account-detail-frame";
import { accountName } from "@/features/accounts/presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useAccountsResetMfa,
  useAccountsRevokeSessions,
  useAccountsRevokeTrustedSessions,
} from "@/lib/api/generated/accounts/accounts";

type SecurityAction = "reset" | "sessions" | "trusted" | null;

function countNoun(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function countLabel(count: number, noun: string): string {
  return `${countNoun(count, noun)} ${count === 1 ? "was" : "were"}`;
}

export function AccountSecurity() {
  const account = useManagedAccount();
  const { user } = usePortalSession();
  const self = user.id === account.id;
  const invalidate = useInvalidateManagedAccount(account.id);
  const action = useManagedAction();
  const reset = useAccountsResetMfa();
  const revokeSessions = useAccountsRevokeSessions();
  const revokeTrusted = useAccountsRevokeTrustedSessions();
  const [confirm, setConfirm] = useState<SecurityAction>(null);
  const busy =
    reset.isPending || revokeSessions.isPending || revokeTrusted.isPending;

  async function confirmAction() {
    const kind = confirm;
    if (!kind) return;
    if (kind === "reset") {
      const result = await action.run(
        () => reset.mutateAsync({ userId: account.id }),
        "Multi-factor authentication could not be reset.",
        () => setConfirm(null),
      );
      if (!result) return;
      setConfirm(null);
      await invalidate();
      action.setNotice(
        `Multi-factor authentication was reset. ${countNoun(result.data.revoked_session_count, "session")} and ${countNoun(result.data.revoked_trusted_session_count, "trusted-browser authorization")} were revoked.`,
      );
      return;
    }
    if (kind === "sessions") {
      const result = await action.run(
        () => revokeSessions.mutateAsync({ userId: account.id }),
        "Sessions could not be signed out.",
        () => setConfirm(null),
      );
      if (!result) return;
      setConfirm(null);
      action.setNotice(
        `${countLabel(result.data.revoked_count, "authentication session")} signed out.`,
      );
      return;
    }
    const result = await action.run(
      () => revokeTrusted.mutateAsync({ userId: account.id }),
      "Trusted-browser authorizations could not be removed.",
      () => setConfirm(null),
    );
    if (!result) return;
    setConfirm(null);
    action.setNotice(
      `${countLabel(result.data.revoked_count, "trusted-browser authorization")} removed.`,
    );
  }

  const name = accountName(account);
  const title =
    confirm === "reset"
      ? `Reset ${name}'s multi-factor authentication?`
      : confirm === "sessions"
        ? `Sign out all of ${name}'s sessions?`
        : `Remove all of ${name}'s trusted browsers?`;
  const description =
    confirm === "reset"
      ? "This removes the account's current authenticator setup and recovery codes. Existing sessions and trusted-browser access will be revoked. The account may need to configure MFA again at the next sign-in."
      : confirm === "sessions"
        ? "This signs the account out of all active COMPASS sessions. Trusted-browser authorizations are separate."
        : "This removes trusted-browser authorization for this account. Future sign-ins may require multi-factor verification again. Authentication sessions are separate.";
  const submitLabel =
    confirm === "reset"
      ? "Reset MFA"
      : confirm === "sessions"
        ? "Sign out all sessions"
        : "Remove all trusted browsers";
  const pendingLabel =
    confirm === "reset"
      ? "Resetting MFA…"
      : confirm === "sessions"
        ? "Signing out…"
        : "Removing trusted browsers…";

  return (
    <section aria-labelledby="managed-security-heading">
      <h2
        id="managed-security-heading"
        className="font-heading text-xl font-semibold text-ink"
      >
        Managed account security
      </h2>
      {self ? (
        <p className="mt-4 text-sm text-muted">
          Use your{" "}
          <Link
            href="/portal/account/security"
            className="font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Account security settings
          </Link>{" "}
          to manage your own authentication.
        </p>
      ) : (
        <div className="mt-5 divide-y divide-border border-y border-border">
          <div className="flex flex-wrap items-start justify-between gap-4 py-5">
            <div>
              <h3 className="font-semibold text-ink">
                Multi-factor authentication
              </h3>
              <p className="mt-1 text-sm text-muted">
                {account.mfa_enabled ? "Enabled" : "Not enabled"}
              </p>
              <p className="mt-2 max-w-2xl text-sm text-muted">
                Resetting removes the authenticator setup and recovery codes and
                revokes sessions and trusted browsers.
              </p>
            </div>
            <Button variant="danger" onClick={() => setConfirm("reset")}>
              Reset MFA
            </Button>
          </div>
          <div className="flex flex-wrap items-start justify-between gap-4 py-5">
            <div>
              <h3 className="font-semibold text-ink">
                Authentication sessions
              </h3>
              <p className="mt-2 max-w-2xl text-sm text-muted">
                Sign out this account from all active sessions.
              </p>
            </div>
            <Button variant="secondary" onClick={() => setConfirm("sessions")}>
              Sign out all sessions
            </Button>
          </div>
          <div className="flex flex-wrap items-start justify-between gap-4 py-5">
            <div>
              <h3 className="font-semibold text-ink">Trusted browsers</h3>
              <p className="mt-2 max-w-2xl text-sm text-muted">
                Remove all saved trusted-browser authorizations for this
                account.
              </p>
            </div>
            <Button variant="secondary" onClick={() => setConfirm("trusted")}>
              Remove all trusted browsers
            </Button>
          </div>
        </div>
      )}
      <ManagedActionFeedback action={action} />
      <AlertDialog
        open={confirm !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setConfirm(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
          {action.error ? (
            <p role="alert" className="mt-3 text-sm text-danger">
              {action.error}
            </p>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={busy}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant={confirm === "reset" ? "danger" : "primary"}
              disabled={busy}
              onClick={() => void confirmAction()}
            >
              {busy ? pendingLabel : submitLabel}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

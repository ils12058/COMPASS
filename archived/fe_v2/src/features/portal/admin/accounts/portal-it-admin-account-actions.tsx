"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Laptop, LockKeyhole, Power, ShieldAlert, Smartphone } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getAccountsGetEffectiveAccessQueryKey,
  getAccountsGetQueryKey,
  getAccountsListQueryKey,
  useAccountsDisable,
  useAccountsEnable,
  useAccountsResetMfa,
  useAccountsRevokeSessions,
  useAccountsRevokeTrustedSessions,
} from "@/lib/api/generated/accounts/accounts";
import type { AccountDetailResponse } from "@/lib/api/generated/model";
import {
  AccountActionMessage,
  AccountSection,
  AccountStatusBadge,
  accountAdminError,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";

type AdminConfirmationRequest = {
  confirmLabel: string;
  description: string;
  run: () => Promise<void>;
  title: string;
};

function AdminConfirmationDialog({
  onOpenChange,
  request,
}: {
  onOpenChange: (open: boolean) => void;
  request: AdminConfirmationRequest | null;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!request) {
    return null;
  }

  const currentRequest = request;

  async function run() {
    setError(null);
    setPending(true);

    try {
      await currentRequest.run();
      onOpenChange(false);
    } catch (caught) {
      setError(accountAdminError(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <AlertDialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) {
          onOpenChange(false);
        }
      }}
    >
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogTitle>{currentRequest.title}</AlertDialogTitle>
          <AlertDialogDescription>{currentRequest.description}</AlertDialogDescription>
        </AlertDialogHeader>
        {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={pending}
            onClick={(event) => {
              event.preventDefault();
              void run();
            }}
          >
            {pending ? "Working…" : currentRequest.confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function PortalItAdminAccountActions({
  account,
}: {
  account: AccountDetailResponse;
}) {
  const queryClient = useQueryClient();
  const [request, setRequest] = useState<AdminConfirmationRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const disableAccount = useAccountsDisable();
  const enableAccount = useAccountsEnable();
  const resetMfa = useAccountsResetMfa();
  const revokeSessions = useAccountsRevokeSessions();
  const revokeTrustedSessions = useAccountsRevokeTrustedSessions();

  async function refreshAccount() {
    await queryClient.invalidateQueries({ queryKey: getAccountsGetQueryKey(account.id) });
    await queryClient.invalidateQueries({ queryKey: getAccountsListQueryKey() });
    await queryClient.invalidateQueries({ queryKey: getAccountsGetEffectiveAccessQueryKey(account.id) });
  }

  function confirmAccountStatusChange() {
    const nextActive = !account.is_active;
    setError(null);
    setMessage(null);
    setRequest({
      title: nextActive ? "Enable this account?" : "Disable this account?",
      description: nextActive
        ? "This account will be allowed to sign in again."
        : "This account will no longer be allowed to sign in. Existing access may also be affected.",
      confirmLabel: nextActive ? "Enable account" : "Disable account",
      run: async () => {
        if (nextActive) {
          await enableAccount.mutateAsync({ userId: account.id });
        } else {
          await disableAccount.mutateAsync({ userId: account.id });
        }
        await refreshAccount();
        setMessage(nextActive ? "The account is enabled." : "The account is disabled.");
      },
    });
  }

  function confirmResetMfa() {
    setError(null);
    setMessage(null);
    setRequest({
      title: "Reset two-step verification?",
      description: "This removes the account’s current authenticator setup and signs out its trusted access. The account will need to set up two-step verification again.",
      confirmLabel: "Reset verification",
      run: async () => {
        const response = await resetMfa.mutateAsync({ userId: account.id });
        await refreshAccount();
        setMessage(
          `Two-step verification was reset. ${response.data.revoked_session_count} active session${response.data.revoked_session_count === 1 ? "" : "s"} and ${response.data.revoked_trusted_session_count} trusted browser${response.data.revoked_trusted_session_count === 1 ? "" : "s"} were revoked.`,
        );
      },
    });
  }

  function confirmRevokeSessions() {
    setError(null);
    setMessage(null);
    setRequest({
      title: "Revoke all active sessions?",
      description: "Every active sign-in session for this account will be ended. The account owner will need to sign in again.",
      confirmLabel: "Revoke sessions",
      run: async () => {
        const response = await revokeSessions.mutateAsync({ userId: account.id });
        await refreshAccount();
        setMessage(`${response.data.revoked_count} active session${response.data.revoked_count === 1 ? "" : "s"} revoked.`);
      },
    });
  }

  function confirmRevokeTrustedSessions() {
    setError(null);
    setMessage(null);
    setRequest({
      title: "Revoke trusted browsers?",
      description: "Every trusted browser for this account will need to complete verification again before it can be trusted.",
      confirmLabel: "Revoke trusted browsers",
      run: async () => {
        const response = await revokeTrustedSessions.mutateAsync({ userId: account.id });
        await refreshAccount();
        setMessage(`${response.data.revoked_count} trusted browser${response.data.revoked_count === 1 ? "" : "s"} revoked.`);
      },
    });
  }

  return (
    <>
      <div className="grid gap-5 xl:grid-cols-2">
        <AccountSection
          icon={Power}
          title="Account status"
          description="Control whether this account can sign in to COMPASS."
        >
          <div className="flex flex-col gap-4 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <AccountStatusBadge active={account.is_active} />
                <span className="text-sm font-semibold">{account.is_active ? "Sign-in allowed" : "Sign-in blocked"}</span>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {account.is_active
                  ? "Disable the account when access should be stopped."
                  : "Enable the account when access should be restored."}
              </p>
            </div>
            <Button type="button" variant={account.is_active ? "destructive" : "default"} onClick={confirmAccountStatusChange}>
              <Power aria-hidden="true" />
              {account.is_active ? "Disable account" : "Enable account"}
            </Button>
          </div>
        </AccountSection>

        <AccountSection
          icon={ShieldAlert}
          title="Sign-in security"
          description="Reset two-step verification or revoke the account’s existing access."
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
              <Smartphone aria-hidden="true" className="size-5 text-[var(--compass-brand-maroon)]" />
              <p className="mt-3 text-sm font-semibold">Two-step verification</p>
              <Badge variant={account.mfa_enabled ? "secondary" : "outline"} className="mt-2">
                {account.mfa_enabled ? "Enabled" : "Not enabled"}
              </Badge>
              {account.mfa_enabled ? (
                <Button type="button" variant="outline" size="sm" className="mt-4 w-full" onClick={confirmResetMfa}>
                  Reset MFA
                </Button>
              ) : null}
            </div>
            <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
              <LockKeyhole aria-hidden="true" className="size-5 text-[var(--compass-brand-maroon)]" />
              <p className="mt-3 text-sm font-semibold">Active sessions</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">End all current sign-ins.</p>
              <Button type="button" variant="outline" size="sm" className="mt-4 w-full" onClick={confirmRevokeSessions}>
                Revoke sessions
              </Button>
            </div>
            <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
              <Laptop aria-hidden="true" className="size-5 text-[var(--compass-brand-maroon)]" />
              <p className="mt-3 text-sm font-semibold">Trusted browsers</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Ask all browsers to verify again.</p>
              <Button type="button" variant="outline" size="sm" className="mt-4 w-full" onClick={confirmRevokeTrustedSessions}>
                Revoke trust
              </Button>
            </div>
          </div>
          <p className="mt-4 text-xs leading-5 text-muted-foreground">
            These controls affect all matching sessions for the account; individual session records are not exposed by this administration view.
          </p>
        </AccountSection>
      </div>

      <AccountActionMessage error={error} message={message} />
      <AdminConfirmationDialog
        request={request}
        onOpenChange={(open) => {
          if (!open) {
            setRequest(null);
          }
        }}
      />
    </>
  );
}

export type { AdminConfirmationRequest };

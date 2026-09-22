"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw, ShieldCheck, Smartphone } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RecoveryCodesPanel } from "@/features/auth/components/recovery-codes-panel";
import { TotpSetup } from "@/features/auth/components/totp-setup";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  useAuthConfirmTotpSetup,
  useAuthDisableTotp,
  useAuthGetMfaStatus,
  useAuthRegenerateRecoveryCodes,
  useAuthStartTotpSetup,
} from "@/lib/api/generated/auth/auth";
import type { TOTPSetupResponse } from "@/lib/api/generated/model";
import type { RequestSecurityConfirmation } from "@/features/portal/account/portal-account-security-shared";
import {
  SecurityMessage,
  SecuritySectionHeading,
  securityError,
} from "@/features/portal/account/portal-account-security-shared";

export function PortalAccountSecurityMfa({
  onRequestConfirmation,
}: {
  onRequestConfirmation: RequestSecurityConfirmation;
}) {
  const queryClient = useQueryClient();
  const [setup, setSetup] = useState<TOTPSetupResponse | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const statusQuery = useAuthGetMfaStatus({
    query: { retry: false, staleTime: 30_000 },
  });
  const startSetup = useAuthStartTotpSetup();
  const confirmSetup = useAuthConfirmTotpSetup();
  const disableTotp = useAuthDisableTotp();
  const regenerateCodes = useAuthRegenerateRecoveryCodes();
  const status = statusQuery.data?.data;

  async function startMfaSetup() {
    setError(null);
    setMessage(null);

    try {
      const response = await startSetup.mutateAsync();
      setSetup(response.data);
    } catch (caught) {
      setError(securityError(caught, "We couldn’t start two-step verification. Please try again."));
    }
  }

  async function confirmMfaSetup(code: string) {
    setError(null);

    try {
      const response = await confirmSetup.mutateAsync({ data: { code } });
      setSetup(null);
      setRecoveryCodes(response.data.recovery_codes);
      setMessage("Two-step verification is now enabled.");
      await queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() });
      await queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() });
    } catch (caught) {
      setError(securityError(caught, "We couldn’t verify that code. Please try again."));
    }
  }

  function confirmDisableMfa() {
    onRequestConfirmation({
      title: "Turn off two-step verification?",
      description: "Sign-in will no longer ask for an authenticator code on this account. You can set it up again later.",
      confirmLabel: "Turn off verification",
      run: async () => {
        await disableTotp.mutateAsync();
        setRecoveryCodes(null);
        setMessage("Two-step verification has been turned off.");
        await queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() });
        await queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() });
      },
    });
  }

  function confirmRegenerateCodes() {
    onRequestConfirmation({
      title: "Create new recovery codes?",
      description: "Your old recovery codes will stop working as soon as the new set is created. Save the new set somewhere secure.",
      confirmLabel: "Create new codes",
      run: async () => {
        const response = await regenerateCodes.mutateAsync();
        setRecoveryCodes(response.data.recovery_codes);
        setMessage("A new set of recovery codes is ready to save.");
      },
    });
  }

  return (
    <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
      <SecuritySectionHeading
        icon={ShieldCheck}
        title="Two-step verification"
        description="Add an authenticator code to your sign-in for another layer of protection."
      />

      {statusQuery.isPending ? (
        <div className="mt-6 h-28 animate-pulse rounded-2xl bg-muted" aria-live="polite" />
      ) : statusQuery.isError ? (
        <p className="mt-6 text-sm text-destructive" role="alert">
          We couldn’t load two-step verification status right now.
        </p>
      ) : setup ? (
        <div className="mt-6 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-5">
          <TotpSetup
            setup={setup}
            busy={confirmSetup.isPending}
            error={error}
            onConfirm={(code) => void confirmMfaSetup(code)}
          />
          <Button type="button" variant="ghost" className="mt-4" onClick={() => setSetup(null)}>
            Cancel setup
          </Button>
        </div>
      ) : recoveryCodes ? (
        <div className="mt-6 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-5">
          <RecoveryCodesPanel
            codes={recoveryCodes}
            doneLabel="I saved these codes"
            onDone={() => setRecoveryCodes(null)}
          />
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          <div className="flex flex-col gap-4 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-card text-[var(--compass-brand-maroon)]">
                <Smartphone aria-hidden="true" className="size-5" />
              </div>
              <div>
                <p className="font-semibold">Authenticator app</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {status?.enabled ? "Enabled for this account." : "Not set up yet."}
                </p>
              </div>
            </div>
            <Badge variant={status?.enabled ? "secondary" : "outline"}>
              {status?.enabled ? "Enabled" : "Not enabled"}
            </Badge>
          </div>

          <div className="flex flex-wrap gap-3">
            {status?.enabled ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  onClick={confirmRegenerateCodes}
                  disabled={regenerateCodes.isPending}
                >
                  <RefreshCw aria-hidden="true" />
                  {regenerateCodes.isPending ? "Creating…" : "Regenerate recovery codes"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={confirmDisableMfa}
                  disabled={disableTotp.isPending}
                >
                  Turn off verification
                </Button>
              </>
            ) : (
              <Button type="button" onClick={() => void startMfaSetup()} disabled={startSetup.isPending}>
                <ShieldCheck aria-hidden="true" />
                {startSetup.isPending ? "Preparing…" : "Set up authenticator"}
              </Button>
            )}
          </div>
        </div>
      )}

      {!setup ? (
        <div className="mt-5">
          <SecurityMessage error={error} message={message} />
        </div>
      ) : null}
    </section>
  );
}

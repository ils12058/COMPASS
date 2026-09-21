"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RecoveryCodesPanel } from "@/features/auth/components/recovery-codes-panel";
import { TotpSetup } from "@/features/auth/components/totp-setup";
import { TotpStepUp } from "@/features/auth/components/totp-step-up";
import { friendlyAuthError, getApiErrorCode } from "@/features/auth/utils/errors";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  getAuthListTrustedSessionsQueryKey,
  useAuthConfirmTotpSetup,
  useAuthDisableTotp,
  useAuthGetMfaStatus,
  useAuthRegenerateRecoveryCodes,
  useAuthStartTotpSetup,
} from "@/lib/api/generated/auth/auth";
import type { TOTPSetupResponse } from "@/lib/api/generated/model";

type SensitiveMfaAction = "disable" | "regenerate";

export function MfaSecurityPanel() {
  const queryClient = useQueryClient();
  const status = useAuthGetMfaStatus({ query: { retry: false } });
  const startSetup = useAuthStartTotpSetup();
  const confirmSetup = useAuthConfirmTotpSetup();
  const disableTotp = useAuthDisableTotp();
  const regenerate = useAuthRegenerateRecoveryCodes();

  const [setup, setSetup] = useState<TOTPSetupResponse | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [stepUpAction, setStepUpAction] = useState<SensitiveMfaAction | null>(null);
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const mfa = status.data?.data;

  async function refreshMfaState(includeTrusted = false) {
    const invalidations = [
      queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() }),
    ];

    if (includeTrusted) {
      invalidations.push(
        queryClient.invalidateQueries({ queryKey: getAuthListTrustedSessionsQueryKey() }),
      );
    }

    await Promise.all(invalidations);
  }

  async function beginEnrollment() {
    setError(null);
    setNotice(null);

    try {
      const response = await startSetup.mutateAsync();
      setSetup(response.data);
    } catch (caught) {
      setError(friendlyAuthError(caught, "Two-step verification setup could not be started."));
    }
  }

  async function confirmEnrollment(code: string) {
    setError(null);

    try {
      const response = await confirmSetup.mutateAsync({ data: { code } });
      setSetup(null);
      setRecoveryCodes(response.data.recovery_codes);
      await refreshMfaState();
    } catch (caught) {
      setError(
        friendlyAuthError(caught, "The authenticator code could not be verified."),
      );
    }
  }

  function requestSensitiveAction(action: SensitiveMfaAction) {
    setError(null);
    setNotice(null);

    if (!mfa?.recent) {
      setStepUpAction(action);
      return;
    }

    if (action === "disable") {
      setConfirmDisable(true);
      return;
    }

    void regenerateCodes();
  }

  async function regenerateCodes() {
    setError(null);

    try {
      const response = await regenerate.mutateAsync();
      setRecoveryCodes(response.data.recovery_codes);
      await refreshMfaState();
    } catch (caught) {
      if (getApiErrorCode(caught) === "recent_mfa_required") {
        setStepUpAction("regenerate");
        return;
      }
      setError(friendlyAuthError(caught, "Recovery codes could not be regenerated."));
    }
  }

  async function disable() {
    setError(null);
    setConfirmDisable(false);

    try {
      await disableTotp.mutateAsync();
      setRecoveryCodes([]);
      await refreshMfaState(true);
      setNotice("Two-step verification has been disabled.");
    } catch (caught) {
      if (getApiErrorCode(caught) === "recent_mfa_required") {
        setStepUpAction("disable");
        return;
      }
      setError(friendlyAuthError(caught, "Two-step verification could not be disabled."));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Two-step verification</CardTitle>
        <CardDescription>
          Add an authenticator to protect sign-in and sensitive account actions.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {status.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Checking two-step verification…
          </p>
        ) : null}

        {status.isError ? (
          <div className="space-y-3">
            <p role="alert" className="text-sm text-destructive">
              Two-step verification status could not be loaded.
            </p>
            <Button variant="outline" onClick={() => status.refetch()}>
              Try again
            </Button>
          </div>
        ) : null}

        {setup ? (
          <TotpSetup
            setup={setup}
            busy={confirmSetup.isPending}
            error={error}
            onConfirm={confirmEnrollment}
          />
        ) : null}

        {recoveryCodes.length ? (
          <RecoveryCodesPanel
            codes={recoveryCodes}
            onDone={() => {
              setRecoveryCodes([]);
              setNotice("Recovery codes acknowledged.");
            }}
          />
        ) : null}

        {stepUpAction ? (
          <TotpStepUp
            onCancel={() => setStepUpAction(null)}
            onVerified={() => {
              setStepUpAction(null);
              setNotice(
                "Verification complete. Choose the security action again when you are ready.",
              );
            }}
          />
        ) : null}

        {confirmDisable ? (
          <section className="space-y-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
            <h3 className="font-heading text-lg font-bold">Disable two-step verification?</h3>
            <p className="text-sm text-muted-foreground">
              Trusted-browser credentials will no longer remain valid. Your current signed-in
              session is managed separately.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="destructive" onClick={disable} disabled={disableTotp.isPending}>
                {disableTotp.isPending ? "Disabling…" : "Disable two-step verification"}
              </Button>
              <Button variant="ghost" onClick={() => setConfirmDisable(false)}>
                Cancel
              </Button>
            </div>
          </section>
        ) : null}

        {!setup && !recoveryCodes.length && !stepUpAction && !confirmDisable && mfa ? (
          mfa.enabled ? (
            <div className="space-y-4">
              <div>
                <p className="font-semibold text-[var(--compass-success)]">Enabled</p>
                <p className="text-sm text-muted-foreground">
                  {mfa.recent
                    ? "Your recent authenticator verification can be used for sensitive actions."
                    : "Sensitive actions may ask for a fresh authenticator code."}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={() => requestSensitiveAction("regenerate")}
                  disabled={regenerate.isPending}
                >
                  Regenerate recovery codes
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => requestSensitiveAction("disable")}
                  disabled={disableTotp.isPending}
                >
                  Disable two-step verification
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Two-step verification is not currently enabled for this account.
              </p>
              <Button onClick={beginEnrollment} disabled={startSetup.isPending}>
                {startSetup.isPending ? "Starting…" : "Set up authenticator"}
              </Button>
            </div>
          )
        ) : null}

        {notice ? (
          <p role="status" aria-live="polite" className="text-sm text-[var(--compass-success)]">
            {notice}
          </p>
        ) : null}

        {error && !setup ? (
          <p role="alert" aria-live="polite" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

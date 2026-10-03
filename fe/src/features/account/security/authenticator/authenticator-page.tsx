"use client";

import { useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { useMemo, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter, PanelHeader, PanelSection } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { PasswordInput } from "@/features/auth/components/password-input";
import { accountErrorCode, accountErrorMessage } from "@/features/account/components/account-errors";
import { SecurityBackLink, StepUpDialog } from "@/features/account/security/security-shared";
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

function manualSecret(uri: string): string | null {
  try {
    const parsed = new URL(uri);
    const secret = parsed.protocol === "otpauth:" ? parsed.searchParams.get("secret") : null;
    return secret && /^[A-Z2-7]+=*$/i.test(secret) ? secret : null;
  } catch {
    return null;
  }
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  async function copy() {
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      setCopied(true);
    } catch {
      setCopyError("The codes could not be copied. Save them manually before leaving this page.");
    }
  }

  return (
    <Panel aria-labelledby="recovery-heading">
      <PanelHeader
        title="Save your recovery codes"
        titleId="recovery-heading"
        description="Each code can be used once if you cannot access your authenticator app. The previous codes, if any, are no longer usable."
      />
      <PanelBody>
      <div aria-label="Recovery codes" className="grid grid-cols-2 gap-3 rounded-sm border border-border bg-surface-subtle p-4 font-mono text-sm text-ink">
        {codes.map((code) => <code key={code} className="break-all">{code}</code>)}
      </div>
      <Button variant="secondary" className="mt-4" onClick={() => void copy()}>{copied ? "Copied" : "Copy all"}</Button>
      {copyError ? <p role="alert" className="mt-3 text-sm text-danger">{copyError}</p> : null}
      <label className="mt-6 flex items-start gap-3 text-sm text-ink">
        <input type="checkbox" className="mt-1 size-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
        <span className="font-semibold">I have saved these recovery codes.</span>
      </label>
      </PanelBody>
      <PanelFooter>
        <Button disabled={!acknowledged} onClick={onDone}>Return to authenticator</Button>
      </PanelFooter>
    </Panel>
  );
}

export function AuthenticatorPage() {
  const queryClient = useQueryClient();
  const mfa = useAuthGetMfaStatus({ query: { retry: false } });
  const start = useAuthStartTotpSetup();
  const confirm = useAuthConfirmTotpSetup();
  const regenerate = useAuthRegenerateRecoveryCodes();
  const disable = useAuthDisableTotp();
  const [setup, setSetup] = useState<TOTPSetupResponse | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [verified, setVerified] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"regenerate" | "disable" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const secret = useMemo(() => setup ? manualSecret(setup.provisioning_uri) : null, [setup]);
  const recent = mfa.data?.data.recent || verified;
  const actionPending = regenerate.isPending || disable.isPending;

  function beginAction(action: "regenerate" | "disable") {
    setError(null);
    setSuccess(null);
    if (!recent) {
      setStepUpOpen(true);
      return;
    }
    setConfirmAction(action);
  }

  async function startSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const response = await start.mutateAsync({ data: { current_password: currentPassword } });
      setSetup(response.data);
    } catch (caught) {
      setError(accountErrorMessage(caught, "Authenticator setup could not be started. Please try again."));
    }
  }

  async function confirmSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const response = await confirm.mutateAsync({ data: { code, current_password: currentPassword } });
      if (!response.data.enabled) {
        setError("Authenticator setup could not be confirmed. Please try again.");
        return;
      }
      setCurrentPassword("");
      setCode("");
      setCodes(response.data.recovery_codes);
      setSetup(null);
      void queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() });
    } catch (caught) {
      if (accountErrorCode(caught) === "mfa_enrollment_authorization_failed") {
        setCurrentPassword("");
        setSetup(null);
        setCode("");
        setError("Your current password could not be verified. Start authenticator setup again.");
        return;
      }
      setError(accountErrorMessage(caught, "The authenticator code could not be verified."));
    }
  }

  async function runConfirmedAction() {
    const action = confirmAction;
    if (!action) return;
    setError(null);
    try {
      if (action === "regenerate") {
        const response = await regenerate.mutateAsync();
        setCodes(response.data.recovery_codes);
      } else {
        await disable.mutateAsync();
        setVerified(false);
        setSuccess("Authenticator disabled.");
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() }),
          queryClient.invalidateQueries({ queryKey: getAuthListTrustedSessionsQueryKey() }),
          queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() }),
        ]);
      }
      setConfirmAction(null);
    } catch (caught) {
      if (accountErrorCode(caught) === "recent_mfa_required") {
        setConfirmAction(null);
        setVerified(false);
        setError("Recent authenticator verification is required. Verify, then select the action again.");
        setStepUpOpen(true);
      } else {
        setError(accountErrorMessage(caught, "The authenticator action could not be completed. Please try again."));
      }
    }
  }

  return (
    <section aria-labelledby="authenticator-heading" className="max-w-2xl">
      <SecurityBackLink />
      <PageHeader title="Authenticator app" headingId="authenticator-heading" />
      {mfa.isPending ? <RowsSkeleton label="Checking authenticator status…" rows={2} framed /> : null}
      {mfa.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void mfa.refetch()}>Retry</Button>}>Authenticator status could not be loaded.</Notice> : null}
      {mfa.isSuccess && codes ? <RecoveryCodes codes={codes} onDone={() => { setCodes(null); setError(null); }} /> : null}
      {mfa.isSuccess && !codes && !mfa.data.data.enabled && !setup ? (
        <Panel as="div">
          <form onSubmit={startSetup}>
            <PanelBody>
            <p className="font-semibold text-ink">Not enabled</p>
            <p className="mt-1 text-sm leading-6 text-muted">Use an authenticator app to add another verification step when signing in.</p>
            <div className="mt-5 grid max-w-md gap-2">
              <Label htmlFor="authenticator-current-password">Current password</Label>
              <PasswordInput
                id="authenticator-current-password"
                name="current-password"
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </div>
            </PanelBody>
            <PanelFooter>
              <Button type="submit" disabled={start.isPending}>{start.isPending ? "Starting setup…" : "Set up authenticator"}</Button>
            </PanelFooter>
          </form>
        </Panel>
      ) : null}
      {mfa.isSuccess && !codes && !mfa.data.data.enabled && setup ? (
        <Panel as="div">
          <PanelHeader title="Scan the setup code" description="Scan this QR code in your authenticator app, then enter its current code." />
          <form onSubmit={confirmSetup}>
          <PanelBody>
          <div className="flex justify-center rounded-sm border border-border bg-surface-raised py-5"><QRCodeSVG value={setup.provisioning_uri} size={220} level="M" marginSize={2} title="Authenticator setup QR code" /></div>
          {secret ? <details className="mt-4 text-sm"><summary className="cursor-pointer font-semibold text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Enter a setup key instead</summary><p className="mt-3 text-muted">Use this key only in your authenticator app:</p><code className="mt-2 block break-all bg-surface-muted p-3 font-mono text-ink">{secret}</code></details> : null}
            <div className="mt-5 grid max-w-xs gap-2"><Label htmlFor="authenticator-setup-code">Authenticator code</Label><Input id="authenticator-setup-code" autoComplete="one-time-code" inputMode="numeric" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value)} /></div>
          </PanelBody>
          <PanelFooter>
            <Button type="submit" disabled={confirm.isPending}>{confirm.isPending ? "Confirming…" : "Confirm authenticator"}</Button>
          </PanelFooter>
          </form>
        </Panel>
      ) : null}
      {mfa.isSuccess && !codes && mfa.data.data.enabled ? (
        <Panel as="div">
          <PanelBody>
            <p className="font-semibold text-ink">Enabled</p>
          </PanelBody>
          <PanelSection title="Recovery codes" titleId="authenticator-recovery-heading" description="Generating new recovery codes invalidates the previous recovery codes.">
            <Button variant="secondary" onClick={() => beginAction("regenerate")}>Generate new recovery codes</Button>
          </PanelSection>
          <PanelSection title="Disable authenticator" titleId="authenticator-disable-heading" description="This removes your authenticator from future sign-ins.">
            <Button variant="quiet" className="text-danger" onClick={() => beginAction("disable")}>Disable authenticator</Button>
          </PanelSection>
        </Panel>
      ) : null}
      {error && confirmAction === null ? <p role="alert" className="mt-5 text-sm text-danger">{error}</p> : null}
      {success ? <p role="status" className="mt-5 text-sm text-success">{success}</p> : null}
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => { setVerified(true); setError(null); setSuccess("Verification complete. Select the action again to continue."); }} />
      <ConsequentialActionDialog
        open={confirmAction !== null}
        title={
          confirmAction === "disable"
            ? "Disable authenticator app?"
            : "Generate new recovery codes?"
        }
        confirmLabel={
          confirmAction === "disable"
            ? "Disable authenticator"
            : "Generate new codes"
        }
        pendingLabel={
          confirmAction === "disable" ? "Disabling…" : "Generating…"
        }
        pending={actionPending}
        error={error}
        variant={confirmAction === "disable" ? "danger" : "primary"}
        onOpenChange={(open) => {
          if (!open) setConfirmAction(null);
        }}
        onConfirm={() => void runConfirmedAction()}
      >
        <p>
          {confirmAction === "disable"
            ? "You will no longer use this authenticator for sign-in. Existing recovery codes will no longer be usable, and trusted-browser state may be revoked."
            : "Generating new recovery codes invalidates the previous recovery codes. Save the new codes when they appear."}
        </p>
      </ConsequentialActionDialog>
    </section>
  );
}

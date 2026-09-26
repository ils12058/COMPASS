"use client";

import { useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { useMemo, useState, type FormEvent } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    <section aria-labelledby="recovery-heading" className="mt-7 border-t border-border pt-7">
      <h2 id="recovery-heading" className="font-heading text-2xl font-semibold text-ink">Save your recovery codes</h2>
      <p className="mt-2 text-sm leading-6 text-muted">Each code can be used once if you cannot access your authenticator app. The previous codes, if any, are no longer usable.</p>
      <div aria-label="Recovery codes" className="mt-5 grid grid-cols-2 gap-3 border-y border-border bg-surface-subtle p-4 font-mono text-sm text-ink">
        {codes.map((code) => <code key={code} className="break-all">{code}</code>)}
      </div>
      <Button variant="secondary" className="mt-4" onClick={() => void copy()}>{copied ? "Copied" : "Copy all"}</Button>
      {copyError ? <p role="alert" className="mt-3 text-sm text-danger">{copyError}</p> : null}
      <label className="mt-6 flex items-start gap-3 text-sm text-ink">
        <input type="checkbox" className="mt-1 size-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
        <span className="font-semibold">I have saved these recovery codes.</span>
      </label>
      <Button className="mt-5" disabled={!acknowledged} onClick={onDone}>Return to authenticator</Button>
    </section>
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

  async function startSetup() {
    setError(null);
    try {
      const response = await start.mutateAsync();
      setSetup(response.data);
    } catch (caught) {
      setError(accountErrorMessage(caught, "Authenticator setup could not be started. Please try again."));
    }
  }

  async function confirmSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const response = await confirm.mutateAsync({ data: { code } });
      if (!response.data.enabled) {
        setError("Authenticator setup could not be confirmed. Please try again.");
        return;
      }
      setCode("");
      setCodes(response.data.recovery_codes);
      setSetup(null);
      void queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() });
    } catch (caught) {
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
      <h1 id="authenticator-heading" className="font-heading text-3xl font-bold text-ink">Authenticator app</h1>
      {mfa.isPending ? <p role="status" className="mt-7 text-sm text-muted">Checking authenticator status…</p> : null}
      {mfa.isError ? <div role="alert" className="mt-7"><p className="text-sm text-danger">Authenticator status could not be loaded.</p><Button variant="secondary" className="mt-3" onClick={() => void mfa.refetch()}>Retry</Button></div> : null}
      {mfa.isSuccess && codes ? <RecoveryCodes codes={codes} onDone={() => { setCodes(null); setError(null); }} /> : null}
      {mfa.isSuccess && !codes && !mfa.data.data.enabled && !setup ? (
        <div className="mt-7 border-t border-border pt-6">
          <p className="font-semibold text-ink">Not enabled</p>
          <p className="mt-2 text-sm leading-6 text-muted">Use an authenticator app to add another verification step when signing in.</p>
          <Button className="mt-5" disabled={start.isPending} onClick={() => void startSetup()}>{start.isPending ? "Starting setup…" : "Set up authenticator"}</Button>
        </div>
      ) : null}
      {mfa.isSuccess && !codes && !mfa.data.data.enabled && setup ? (
        <div className="mt-7 border-t border-border pt-6">
          <h2 className="font-heading text-xl font-semibold text-ink">Scan the setup code</h2>
          <p className="mt-2 text-sm text-muted">Scan this QR code in your authenticator app, then enter its current code.</p>
          <div className="mt-5 flex justify-center border-y border-border bg-surface-raised py-5"><QRCodeSVG value={setup.provisioning_uri} size={220} level="M" marginSize={2} title="Authenticator setup QR code" /></div>
          {secret ? <details className="mt-4 border-b border-border pb-4 text-sm"><summary className="cursor-pointer font-semibold text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Enter a setup key instead</summary><p className="mt-3 text-muted">Use this key only in your authenticator app:</p><code className="mt-2 block break-all bg-surface-muted p-3 font-mono text-ink">{secret}</code></details> : null}
          <form className="mt-6 space-y-5" onSubmit={confirmSetup}>
            <div className="grid gap-2"><Label htmlFor="authenticator-setup-code">Authenticator code</Label><Input id="authenticator-setup-code" autoComplete="one-time-code" inputMode="numeric" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value)} /></div>
            <Button type="submit" disabled={confirm.isPending}>{confirm.isPending ? "Confirming…" : "Confirm authenticator"}</Button>
          </form>
        </div>
      ) : null}
      {mfa.isSuccess && !codes && mfa.data.data.enabled ? (
        <div className="mt-7 space-y-6 border-t border-border pt-6">
          <p className="font-semibold text-ink">Enabled</p>
          <div className="border-t border-border pt-5"><h2 className="font-heading text-xl font-semibold text-ink">Recovery codes</h2><p className="mt-2 text-sm leading-6 text-muted">Generating new recovery codes invalidates the previous recovery codes.</p><Button variant="secondary" className="mt-4" onClick={() => beginAction("regenerate")}>Generate new recovery codes</Button></div>
          <div className="border-t border-border pt-5"><h2 className="font-heading text-xl font-semibold text-ink">Disable authenticator</h2><p className="mt-2 text-sm leading-6 text-muted">This removes your authenticator from future sign-ins.</p><Button variant="quiet" className="mt-3 text-danger" onClick={() => beginAction("disable")}>Disable authenticator</Button></div>
        </div>
      ) : null}
      {error ? <p role="alert" className="mt-5 text-sm text-danger">{error}</p> : null}
      {success ? <p role="status" className="mt-5 text-sm text-success">{success}</p> : null}
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => { setVerified(true); setError(null); setSuccess("Verification complete. Select the action again to continue."); }} />
      <AlertDialog open={confirmAction !== null} onOpenChange={(open) => { if (!open && !actionPending) setConfirmAction(null); }}>
        <AlertDialogContent>
          <AlertDialogTitle>{confirmAction === "disable" ? "Disable authenticator app?" : "Generate new recovery codes?"}</AlertDialogTitle>
          <AlertDialogDescription>{confirmAction === "disable" ? "You will no longer use this authenticator for sign-in. Existing recovery codes will no longer be usable, and trusted-browser state may be revoked." : "Generating new recovery codes invalidates the previous recovery codes. Save the new codes when they appear."}</AlertDialogDescription>
          {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialogCancel asChild><Button variant="secondary" disabled={actionPending}>Cancel</Button></AlertDialogCancel>
            <Button variant={confirmAction === "disable" ? "danger" : "primary"} disabled={actionPending} onClick={() => void runConfirmedAction()}>{actionPending ? (confirmAction === "disable" ? "Disabling…" : "Generating…") : (confirmAction === "disable" ? "Disable authenticator" : "Generate new codes")}</Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

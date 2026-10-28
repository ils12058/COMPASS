"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { accountErrorMessage } from "@/features/account/components/account-errors";
import { AUTHENTICATOR_SETUP_HREF, type StepUpRequirement } from "@/features/account/security/step-up";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  useAuthVerifyTotp,
} from "@/lib/api/generated/auth/auth";

export function SecurityBackLink() {
  return (
    <Link href="/portal/account/security" className={pageBackLinkClass}>
      ← Security
    </Link>
  );
}

// Opens for a retained strong-auth action. With an authenticator ("verify") it asks for a current
// code; without one ("setup") it never asks for a code and points to authenticator setup instead.
export function StepUpDialog({
  open,
  onOpenChange,
  onVerified,
  isContinuing = false,
  requirement = "verify",
  setupInNewTab = false,
  reviewAfterVerification = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onVerified?: () => void | Promise<void>;
  isContinuing?: boolean;
  requirement?: StepUpRequirement;
  // Catalog drafts stay in their original tab while Security handles setup.
  setupInNewTab?: boolean;
  reviewAfterVerification?: boolean;
}) {
  if (requirement === "setup") {
    return <AuthenticatorSetupDialog open={open} onOpenChange={onOpenChange} inNewTab={setupInNewTab} />;
  }
  return <AuthenticatorCodeDialog open={open} onOpenChange={onOpenChange} onVerified={onVerified} isContinuing={isContinuing} reviewAfterVerification={reviewAfterVerification} />;
}

function AuthenticatorSetupDialog({
  open,
  onOpenChange,
  inNewTab,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  inNewTab: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Set up an authenticator</DialogTitle>
        <DialogDescription>
          {inNewTab ? "This action needs an authenticator. Open Security in a new tab to keep your draft here. After setup, return here and review the change again." : "This action needs an authenticator app on your account. Set one up in Security, then try the action again."}
        </DialogDescription>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>{inNewTab ? "Return to change" : "Cancel"}</Button>
          <GuardedPortalLink target={inNewTab ? "_blank" : undefined} rel={inNewTab ? "noopener noreferrer" : undefined} href={AUTHENTICATOR_SETUP_HREF} className={buttonVariants({ variant: "primary" })}>
            Set up authenticator{inNewTab ? <span className="sr-only"> (opens in a new tab)</span> : null}
          </GuardedPortalLink>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AuthenticatorCodeDialog({
  open,
  onOpenChange,
  onVerified,
  isContinuing,
  reviewAfterVerification,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onVerified?: () => void | Promise<void>;
  isContinuing: boolean;
  reviewAfterVerification: boolean;
}) {
  const queryClient = useQueryClient();
  const verify = useAuthVerifyTotp();
  const verificationRunning = useRef(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const busy = verify.isPending || completing || isContinuing;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (verificationRunning.current || busy) return;
    verificationRunning.current = true;
    setError(null);
    try {
      await verify.mutateAsync({ data: { code } });
    } catch (caught) {
      setError(accountErrorMessage(caught, "The authenticator code could not be verified."));
      verificationRunning.current = false;
      return;
    }
    setCode("");
    setCompleting(true);
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() }),
      ]);
      await onVerified?.();
      onOpenChange(false);
    } catch {
      setError("Verification succeeded, but the action could not be completed. Review its status before trying again.");
    } finally {
      setCompleting(false);
      verificationRunning.current = false;
    }
  }

  function close() {
    if (busy) return;
    onOpenChange(false);
    setCode("");
    setError(null);
  }

  return (
    <Dialog open={open} onOpenChange={(next) => {
      if (next) onOpenChange(true);
      else close();
    }}>
      <DialogContent dismissible={!busy}>
        <DialogTitle>Verify it&apos;s you</DialogTitle>
        <DialogDescription>
          {reviewAfterVerification ? "Verify your authenticator. You will review the latest details before submitting the change again." : onVerified
            ? "This confirmed action needs a recent security check. Enter the current code from your authenticator app to continue."
            : "Enter the current code from your authenticator app."}
        </DialogDescription>
        <form className="mt-6 space-y-5" onSubmit={submit}>
          <div className="grid gap-2">
            <Label htmlFor="step-up-code">Authenticator code</Label>
            <Input id="step-up-code" autoComplete="one-time-code" inputMode="numeric" maxLength={6} required disabled={busy} value={code} onChange={(event) => setCode(event.target.value)} aria-describedby={error ? "step-up-error" : undefined} />
          </div>
          {error ? <p id="step-up-error" role="alert" className="text-sm text-danger">{error}</p> : null}
          {busy && !verify.isPending ? <p role="status" className="text-sm text-muted">{reviewAfterVerification ? "Verification succeeded. Loading the latest details…" : "Verification succeeded. Completing your action…"}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" disabled={busy} onClick={close}>Cancel</Button>
            <Button type="submit" disabled={busy}>{verify.isPending ? "Verifying…" : busy ? (reviewAfterVerification ? "Loading…" : "Completing…") : "Verify"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

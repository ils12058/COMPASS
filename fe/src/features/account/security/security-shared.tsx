"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

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
  requirement = "verify",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onVerified?: () => void;
  requirement?: StepUpRequirement;
}) {
  if (requirement === "setup") {
    return <AuthenticatorSetupDialog open={open} onOpenChange={onOpenChange} />;
  }
  return <AuthenticatorCodeDialog open={open} onOpenChange={onOpenChange} onVerified={onVerified} />;
}

function AuthenticatorSetupDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Set up an authenticator</DialogTitle>
        <DialogDescription>
          This action needs an authenticator app on your account. Set one up in Security, then try
          the action again.
        </DialogDescription>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <GuardedPortalLink href={AUTHENTICATOR_SETUP_HREF} className={buttonVariants({ variant: "primary" })}>
            Set up authenticator
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
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onVerified?: () => void;
}) {
  const queryClient = useQueryClient();
  const verify = useAuthVerifyTotp();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await verify.mutateAsync({ data: { code } });
      setCode("");
      onOpenChange(false);
      onVerified?.();
    } catch (caught) {
      setError(accountErrorMessage(caught, "The authenticator code could not be verified."));
      return;
    }
    void queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() });
    void queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() });
  }

  function close() {
    onOpenChange(false);
    setCode("");
    setError(null);
  }

  return (
    <Dialog open={open} onOpenChange={(next) => {
      if (next) onOpenChange(true);
      else close();
    }}>
      <DialogContent dismissible={!verify.isPending}>
        <DialogTitle>Verify it&apos;s you</DialogTitle>
        <DialogDescription>Enter the current code from your authenticator app.</DialogDescription>
        <form className="mt-6 space-y-5" onSubmit={submit}>
          <div className="grid gap-2">
            <Label htmlFor="step-up-code">Authenticator code</Label>
            <Input id="step-up-code" autoComplete="one-time-code" inputMode="numeric" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value)} aria-describedby={error ? "step-up-error" : undefined} />
          </div>
          {error ? <p id="step-up-error" role="alert" className="text-sm text-danger">{error}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" disabled={verify.isPending} onClick={close}>Cancel</Button>
            <Button type="submit" disabled={verify.isPending}>{verify.isPending ? "Verifying…" : "Verify"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { accountErrorMessage } from "@/features/account/components/account-errors";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  useAuthVerifyTotp,
} from "@/lib/api/generated/auth/auth";

export function SecurityBackLink() {
  return (
    <Link href="/portal/account/security" className="mb-6 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
      ← Security
    </Link>
  );
}

export function StepUpDialog({
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
      if (verify.isPending) return;
      if (next) onOpenChange(true);
      else close();
    }}>
      <DialogContent onEscapeKeyDown={(event) => { if (verify.isPending) event.preventDefault(); }} onPointerDownOutside={(event) => { if (verify.isPending) event.preventDefault(); }}>
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

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  useAuthVerifyTotp,
} from "@/lib/api/generated/auth/auth";
import { friendlyAuthError } from "@/features/auth/utils/errors";

export function TotpStepUp({
  onVerified,
  onCancel,
}: {
  onVerified: () => void;
  onCancel?: () => void;
}) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const verify = useAuthVerifyTotp();

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    try {
      await verify.mutateAsync({ data: { code: code.trim() } });
      setCode("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() }),
      ]);
      onVerified();
    } catch (caught) {
      setCode("");
      setError(friendlyAuthError(caught, "The authenticator code could not be verified."));
    }
  }

  return (
    <form className="space-y-4 rounded-lg border bg-muted/50 p-4" onSubmit={submit}>
      <div>
        <h3 className="font-heading text-lg font-bold">Verify it’s you</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter a current code from your authenticator to continue.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="step-up-code">Authenticator code</Label>
        <Input
          id="step-up-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]{6}"
          maxLength={6}
          required
        />
      </div>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={verify.isPending || code.trim().length !== 6}>
          {verify.isPending ? "Verifying…" : "Verify"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}

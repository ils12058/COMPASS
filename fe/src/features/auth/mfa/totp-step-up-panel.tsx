"use client";

import { useState, type FormEvent } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authVerifyTotp, getAuthGetMfaStatusQueryKey, getAuthGetSessionQueryKey } from "@/lib/api/generated/auth/auth";
import { CompassApiError, readApiErrorMessage } from "@/lib/api/errors";

function authenticationErrorMessage(error: unknown): string {
  if (error instanceof CompassApiError) {
    return readApiErrorMessage(error.body) ?? "Authenticator verification could not be completed.";
  }
  return "Authenticator verification could not be completed. Check your connection and try again.";
}

export function TotpStepUpPanel({
  onVerified,
  onCancel,
  onPendingChange,
}: {
  onVerified: () => void;
  onCancel: () => void;
  onPendingChange?: (pending: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const verify = useMutation({
    mutationFn: (value: string) => authVerifyTotp({ code: value }),
    retry: false,
    onMutate: () => onPendingChange?.(true),
    onSettled: () => onPendingChange?.(false),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const response = await verify.mutateAsync(code);
      if (!response.data.recent) {
        setCode("");
        setError("Authenticator verification did not establish a recent session. Try again.");
        return;
      }
      setCode("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() }),
      ]);
      onVerified();
    } catch (caught) {
      setCode("");
      setError(authenticationErrorMessage(caught));
    }
  }

  return (
    <form onSubmit={submit} aria-busy={verify.isPending} className="mt-5 space-y-4">
      <div>
        <Label htmlFor="good-moral-totp-code">Authenticator code</Label>
        <Input
          id="good-moral-totp-code"
          className="mt-2"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          required
          aria-describedby={error ? "good-moral-totp-error" : undefined}
        />
      </div>
      {error ? <p id="good-moral-totp-error" role="alert" className="text-sm leading-6 text-danger">{error}</p> : null}
      <div className="flex flex-wrap justify-end gap-3">
        <Button variant="secondary" onClick={onCancel} disabled={verify.isPending}>Cancel</Button>
        <Button type="submit" disabled={verify.isPending || !code.trim()}>{verify.isPending ? "Verifying…" : "Verify"}</Button>
      </div>
    </form>
  );
}

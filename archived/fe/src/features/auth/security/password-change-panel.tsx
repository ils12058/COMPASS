"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TotpStepUp } from "@/features/auth/components/totp-step-up";
import {
  friendlyAuthError,
  getApiErrorCode,
  getPasswordPolicyMessages,
} from "@/features/auth/utils/errors";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  getAuthListSessionsQueryKey,
  getAuthListTrustedSessionsQueryKey,
  useAuthChangePassword,
  useAuthGetMfaStatus,
} from "@/lib/api/generated/auth/auth";

export function PasswordChangePanel() {
  const queryClient = useQueryClient();
  const status = useAuthGetMfaStatus({ query: { retry: false } });
  const changePassword = useAuthChangePassword();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [stepUpRequired, setStepUpRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [policyMessages, setPolicyMessages] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const mfa = status.data?.data;

  function clearPasswords() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }

  async function refreshSecurityState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getAuthGetMfaStatusQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getAuthListSessionsQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getAuthListTrustedSessionsQueryKey() }),
    ]);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPolicyMessages([]);
    setNotice(null);

    if (newPassword !== confirmPassword) {
      setError("The password confirmation does not match.");
      return;
    }

    if (mfa?.enabled && !mfa.recent) {
      clearPasswords();
      setStepUpRequired(true);
      return;
    }

    try {
      await changePassword.mutateAsync({
        data: {
          current_password: mfa?.enabled ? null : currentPassword,
          new_password: newPassword,
        },
      });
      clearPasswords();
      await refreshSecurityState();
      setNotice("Your password has been changed.");
    } catch (caught) {
      clearPasswords();

      if (getApiErrorCode(caught) === "recent_mfa_required") {
        setStepUpRequired(true);
        return;
      }

      if (getApiErrorCode(caught) === "password_policy_failed") {
        setPolicyMessages(getPasswordPolicyMessages(caught));
        setError("Choose a different password and try again.");
        return;
      }

      setError(friendlyAuthError(caught, "Your password could not be changed."));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>
          Change the password for your signed-in COMPASS account.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {status.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Checking account security…
          </p>
        ) : null}

        {status.isError ? (
          <div className="space-y-3">
            <p role="alert" className="text-sm text-destructive">
              Password-change requirements could not be loaded.
            </p>
            <Button variant="outline" onClick={() => status.refetch()}>
              Try again
            </Button>
          </div>
        ) : null}

        {stepUpRequired ? (
          <TotpStepUp
            onCancel={() => setStepUpRequired(false)}
            onVerified={() => {
              setStepUpRequired(false);
              setNotice("Verification complete. Enter your new password to continue.");
            }}
          />
        ) : null}

        {mfa && !stepUpRequired ? (
          <form className="space-y-4" onSubmit={submit}>
            {!mfa.enabled ? (
              <div className="space-y-2">
                <Label htmlFor="current-password-change">Current password</Label>
                <Input
                  id="current-password-change"
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
            ) : (
              <p className="rounded-lg bg-muted p-3 text-sm text-muted-foreground">
                This account uses authenticator verification instead of the current password for
                this security change.
              </p>
            )}

            <div className="space-y-2">
              <Label htmlFor="account-new-password">New password</Label>
              <Input
                id="account-new-password"
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="account-confirm-password">Confirm new password</Label>
              <Input
                id="account-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                required
              />
            </div>

            {policyMessages.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-destructive">
                {policyMessages.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}

            {error ? (
              <p role="alert" aria-live="polite" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}

            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? "Changing password…" : "Change password"}
            </Button>
          </form>
        ) : null}

        {notice ? (
          <p role="status" aria-live="polite" className="text-sm text-[var(--compass-success)]">
            {notice}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

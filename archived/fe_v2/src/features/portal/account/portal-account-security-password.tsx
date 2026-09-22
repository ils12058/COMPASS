"use client";

import { type FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/features/auth/components/password-input";
import { getPasswordPolicyMessages } from "@/features/auth/utils/errors";
import { useAuthChangePassword, getAuthGetSessionQueryKey } from "@/lib/api/generated/auth/auth";
import {
  SecurityMessage,
  SecuritySectionHeading,
  securityError,
} from "@/features/portal/account/portal-account-security-shared";

export function PortalAccountSecurityPassword() {
  const queryClient = useQueryClient();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const changePassword = useAuthChangePassword();
  const passwordPolicyMessages = getPasswordPolicyMessages(changePassword.error);

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
      return;
    }

    if (!newPassword.trim()) {
      setError("Enter a new password to continue.");
      return;
    }

    try {
      await changePassword.mutateAsync({
        data: {
          current_password: currentPassword || null,
          new_password: newPassword,
        },
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("Your password has been updated.");
      await queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() });
    } catch (caught) {
      setError(securityError(caught, "We couldn’t update your password. Please try again."));
    }
  }

  return (
    <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
      <SecuritySectionHeading
        icon={KeyRound}
        title="Password"
        description="Choose a new password for signing in. Keep it unique and avoid sharing it with anyone."
      />
      <form className="mt-6 space-y-5" onSubmit={(event) => void savePassword(event)}>
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="security-current-password">Current password</Label>
            <PasswordInput
              id="security-current-password"
              value={currentPassword}
              autoComplete="current-password"
              placeholder="Leave blank if you have not set one yet"
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="security-new-password">New password</Label>
            <PasswordInput
              id="security-new-password"
              value={newPassword}
              autoComplete="new-password"
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="security-confirm-password">Confirm new password</Label>
            <PasswordInput
              id="security-confirm-password"
              value={confirmPassword}
              autoComplete="new-password"
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </div>
        </div>

        {passwordPolicyMessages.length ? (
          <ul className="list-disc space-y-1 pl-5 text-sm text-destructive">
            {passwordPolicyMessages.map((item) => <li key={item}>{item}</li>)}
          </ul>
        ) : null}
        <SecurityMessage error={error} message={message} />
        <Button type="submit" disabled={changePassword.isPending}>
          <KeyRound aria-hidden="true" />
          {changePassword.isPending ? "Updating…" : "Update password"}
        </Button>
      </form>
    </section>
  );
}

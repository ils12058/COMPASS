"use client";

import { useState } from "react";

import { SecurityConfirmationDialog } from "@/features/portal/account/portal-account-security-shared";
import type { SecurityConfirmationRequest } from "@/features/portal/account/portal-account-security-shared";
import { PortalAccountSecurityEmail } from "@/features/portal/account/portal-account-security-email";
import { PortalAccountSecurityMfa } from "@/features/portal/account/portal-account-security-mfa";
import { PortalAccountSecurityPassword } from "@/features/portal/account/portal-account-security-password";
import { PortalAccountSecuritySessions } from "@/features/portal/account/portal-account-security-sessions";

export function PortalAccountSecurity({
  profile,
}: {
  profile: { email: string } | undefined;
}) {
  const [confirmation, setConfirmation] = useState<SecurityConfirmationRequest | null>(null);

  return (
    <div className="space-y-5">
      <PortalAccountSecurityPassword />
      <PortalAccountSecurityEmail currentEmail={profile?.email ?? "Your current sign-in email"} />
      <PortalAccountSecurityMfa onRequestConfirmation={setConfirmation} />
      <PortalAccountSecuritySessions onRequestConfirmation={setConfirmation} />
      <SecurityConfirmationDialog request={confirmation} onOpenChange={(open) => {
        if (!open) {
          setConfirmation(null);
        }
      }} />
    </div>
  );
}

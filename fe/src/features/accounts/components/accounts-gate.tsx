"use client";

import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

export function AccountsGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  if (!user.capabilities.includes("accounts.manage")) {
    return (
      <WorkspaceUnavailable title="Accounts unavailable">
        Account administration is unavailable to this account.
      </WorkspaceUnavailable>
    );
  }
  return children;
}

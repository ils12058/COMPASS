"use client";

import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { hasPrivacyGovernanceWorkspace } from "@/features/privacy-governance/privacy-governance-access";

export function PrivacyGovernanceGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();

  if (hasPrivacyGovernanceWorkspace(user)) return children;

  return (
    <WorkspaceUnavailable title="Privacy Governance unavailable">
      Your current access does not include Privacy Governance.
    </WorkspaceUnavailable>
  );
}

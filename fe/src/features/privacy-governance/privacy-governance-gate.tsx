"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { canViewPrivacyNotices, canViewPrivacyActivity, hasPrivacyGovernanceWorkspace } from "@/features/privacy-governance/privacy-governance-access";

export function PrivacyGovernanceGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();

  const pathname = usePathname();
  const within = (path: string) => pathname === path || pathname.startsWith(path + "/");
  const allowed = within("/portal/privacy/notices") || within("/portal/privacy/notice-revisions")
    ? canViewPrivacyNotices(user)
    : within("/portal/privacy/activity")
      ? canViewPrivacyActivity(user)
      : hasPrivacyGovernanceWorkspace(user);

  if (allowed) return children;

  return (
    <WorkspaceUnavailable title="Access restricted">
      You don’t have access to Privacy Governance.
    </WorkspaceUnavailable>
  );
}

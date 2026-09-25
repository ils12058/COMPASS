"use client";

import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

function Unavailable({ management = false }: { management?: boolean }) {
  return (
    <WorkspaceUnavailable title="Organization unavailable">
      {management
        ? "Your current access does not include Organization management."
        : "Your current access does not include Organization."}
    </WorkspaceUnavailable>
  );
}

export function OrganizationGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  const allowed =
    user.capabilities.includes("organization.view") ||
    user.capabilities.includes("organization.manage");
  return allowed ? children : <Unavailable />;
}

export function OrganizationManageGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return user.capabilities.includes("organization.manage") ? (
    children
  ) : (
    <Unavailable management />
  );
}

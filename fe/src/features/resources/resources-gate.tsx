"use client";

import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { canManageResources } from "@/features/resources/resources-access";

export function ResourcesGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canManageResources(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Resources unavailable">
      Your current access does not include Resource management.
    </WorkspaceUnavailable>
  );
}

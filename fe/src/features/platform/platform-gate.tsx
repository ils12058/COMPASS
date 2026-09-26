"use client";

import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import type { CapabilityCode } from "@/lib/api/generated/model";

export function hasPlatformView(user: { capabilities: readonly CapabilityCode[] }): boolean {
  return user.capabilities.includes("platform_operations.view");
}

export function hasPlatformManage(user: { capabilities: readonly CapabilityCode[] }): boolean {
  return user.capabilities.includes("platform_operations.manage");
}

export function PlatformGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();

  if (hasPlatformView(user)) return children;

  return (
    <WorkspaceUnavailable title="Platform Operations unavailable">
      Your current access does not include Platform Operations.
    </WorkspaceUnavailable>
  );
}

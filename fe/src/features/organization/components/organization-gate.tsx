"use client";

import type { ReactNode } from "react";

import {
  canManageOrganization,
  canViewOrganizationStructure,
} from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

// Structure reads remain safe reference data for other workflows. The standalone
// Organization workspace is still entered through operational management authority (ADR-064).
export function OrganizationGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canManageOrganization(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Organization unavailable">
      You don’t have access to manage organization records.
    </WorkspaceUnavailable>
  );
}

export function OrganizationStructureGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canViewOrganizationStructure(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Organization structure unavailable">
      You don’t have access to campus, college, and program information.
    </WorkspaceUnavailable>
  );
}

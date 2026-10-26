"use client";

import type { ReactNode } from "react";

import {
  canManageOrganization,
  canEnterOrganization,
  canViewOrganizationStructure,
} from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

export function OrganizationGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canEnterOrganization(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Organization unavailable">
      You don’t have access to the Organization workspace.
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

export function OrganizationRelationshipsGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canManageOrganization(user) ? children : (
    <WorkspaceUnavailable title="Organization relationships unavailable">
      You don’t have access to manage organization relationships.
    </WorkspaceUnavailable>
  );
}

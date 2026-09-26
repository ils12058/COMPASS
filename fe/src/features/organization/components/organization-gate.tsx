"use client";

import type { ReactNode } from "react";

import {
  canManageOrganization,
  canViewOrganizationStructure,
} from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

// Structure reads alone are reference data for selectors in other workflows;
// the Organization workspace follows management authority (ADR-059).
export function OrganizationGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canManageOrganization(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Organization unavailable">
      Your current access does not include Organization management.
    </WorkspaceUnavailable>
  );
}

export function OrganizationStructureGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canViewOrganizationStructure(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Organization structure unavailable">
      Your current access does not include Campus, College, and Program structure.
    </WorkspaceUnavailable>
  );
}

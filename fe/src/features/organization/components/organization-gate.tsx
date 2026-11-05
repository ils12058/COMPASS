"use client";

import type { ReactNode } from "react";

import {
  canManageOrganization,
  canEnterOrganization,
  canViewOrganizationStructure,
} from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  canImportStudentAcademics,
  canViewOwnAcademicRecord,
  canViewStudentAcademics,
} from "@/features/student-academics/student-academics-access";

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

export function StudentAcademicRecordsGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canViewStudentAcademics(user) ? children : (
    <WorkspaceUnavailable title="Student Academic Records unavailable">
      You don’t have access to Student academic records.
    </WorkspaceUnavailable>
  );
}

export function StudentAcademicRosterImportGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canImportStudentAcademics(user) ? children : (
    <WorkspaceUnavailable title="Academic roster import unavailable">
      You don’t have access to import academic rosters.
    </WorkspaceUnavailable>
  );
}

export function MyAcademicRecordGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return canViewOwnAcademicRecord(user) ? children : (
    <WorkspaceUnavailable title="Academic record unavailable">
      You don’t have access to your academic record.
    </WorkspaceUnavailable>
  );
}

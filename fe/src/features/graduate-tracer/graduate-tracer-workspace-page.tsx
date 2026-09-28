"use client";

import type { GraduateTracerOperationalFilters } from "@/features/graduate-tracer/graduate-tracer-operational-list";
import { GraduateTracerOperationalList } from "@/features/graduate-tracer/graduate-tracer-operational-list";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { GraduateTracerStudentWorkspace } from "@/features/graduate-tracer/graduate-tracer-student-workspace";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

export function GraduateTracerWorkspacePage({ filters }: { filters: GraduateTracerOperationalFilters }) {
  const { user } = usePortalSession();
  const access = getGraduateTracerAccess(user);

  if (access.hasStudentWorkspace) return <GraduateTracerStudentWorkspace access={access} />;
  if (access.hasOperationalWorkspace) return <GraduateTracerOperationalList filters={filters} />;

  return (
    <WorkspaceUnavailable title="Graduate Tracer unavailable">
      Your current access does not include a Graduate Tracer workspace.
    </WorkspaceUnavailable>
  );
}

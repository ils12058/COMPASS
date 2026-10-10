"use client";

import { pageSheetWidth } from "@/components/ui/page-width";
import type { GraduateTracerOperationalFilters } from "@/features/graduate-tracer/graduate-tracer-operational-list";
import { GraduateTracerOperationalList } from "@/features/graduate-tracer/graduate-tracer-operational-list";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { GraduateTracerStudentWorkspace } from "@/features/graduate-tracer/graduate-tracer-student-workspace";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";

export function GraduateTracerWorkspacePage({ filters }: { filters: GraduateTracerOperationalFilters }) {
  const { user } = usePortalSession();
  const access = getGraduateTracerAccess(user);

  if (access.hasStudentWorkspace) {
    return (
      <div className={pageSheetWidth}>
        <GraduateTracerStudentWorkspace access={access} />
      </div>
    );
  }
  if (access.hasOperationalWorkspace) return <GraduateTracerOperationalList filters={filters} />;

  if (access.isStudent && !access.isGraduatedStudent) {
    return (
      <WorkspaceUnavailable title="Graduate Tracer unavailable">
        The Graduate Tracer Survey is for graduates.
      </WorkspaceUnavailable>
    );
  }

  return (
    <WorkspaceUnavailable title="Graduate Tracer unavailable">
      You don’t have access to Graduate Tracer.
    </WorkspaceUnavailable>
  );
}

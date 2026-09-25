"use client";

import type { GraduateTracerOperationalFilters } from "@/features/graduate-tracer/graduate-tracer-operational-list";
import { GraduateTracerOperationalList } from "@/features/graduate-tracer/graduate-tracer-operational-list";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { GraduateTracerStudentWorkspace } from "@/features/graduate-tracer/graduate-tracer-student-workspace";
import { GraduateTracerHeading } from "@/features/graduate-tracer/graduate-tracer-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function GraduateTracerWorkspacePage({ filters }: { filters: GraduateTracerOperationalFilters }) {
  const { user } = usePortalSession();
  const access = getGraduateTracerAccess(user);

  if (access.isStudent) return <GraduateTracerStudentWorkspace access={access} />;
  if (access.canViewOperational) return <GraduateTracerOperationalList filters={filters} />;

  return (
    <section className="space-y-6">
      <GraduateTracerHeading title="Graduate Tracer Survey" />
      <p role="alert" className="border-y border-border py-5 text-sm leading-6 text-muted">Your current access does not include a Graduate Tracer workspace.</p>
    </section>
  );
}

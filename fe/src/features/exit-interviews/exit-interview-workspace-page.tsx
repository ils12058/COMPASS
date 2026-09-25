"use client";

import type { ExitInterviewOperationalFilters } from "@/features/exit-interviews/exit-interview-operational-list";
import { ExitInterviewOperationalList } from "@/features/exit-interviews/exit-interview-operational-list";
import { ExitInterviewStudentHome } from "@/features/exit-interviews/exit-interview-student-home";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { ExitInterviewUnavailable } from "@/features/exit-interviews/exit-interview-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function ExitInterviewWorkspacePage({
  filters,
  notice,
}: {
  filters: ExitInterviewOperationalFilters;
  notice?: "reopened";
}) {
  const { user } = usePortalSession();
  const access = getExitInterviewAccess(user);

  if (access.isStudent) {
    return <ExitInterviewStudentHome access={access} />;
  }

  if (access.canViewOperational) {
    return <ExitInterviewOperationalList filters={filters} notice={notice} />;
  }

  return (
    <ExitInterviewUnavailable
      title="Exit Interview unavailable"
      message={
        access.canReopen
          ? "Your current access allows correction reopening but does not include the Exit Interview review queue. Contact the administrator if you need review access."
          : undefined
      }
    />
  );
}

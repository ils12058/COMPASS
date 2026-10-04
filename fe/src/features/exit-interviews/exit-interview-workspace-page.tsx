"use client";

import { pageSheetWidth } from "@/components/ui/page-width";
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

  if (access.isStudent && access.hasStudentWorkspace) {
    return (
      <div className={pageSheetWidth}>
        <ExitInterviewStudentHome access={access} />
      </div>
    );
  }

  if (access.hasOperationalWorkspace) {
    return <ExitInterviewOperationalList filters={filters} notice={notice} />;
  }

  return <ExitInterviewUnavailable title="Exit Interview unavailable" />;
}

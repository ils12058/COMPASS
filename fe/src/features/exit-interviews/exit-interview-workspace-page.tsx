"use client";

import Link from "next/link";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";
import { ExitInterviewOpportunitiesPage } from "@/features/exit-interviews/exit-interview-opportunities-page";
import type { ExitInterviewsListOpportunitiesParams } from "@/lib/api/generated/model";

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
  opportunities,
}: {
  filters: ExitInterviewOperationalFilters;
  notice?: "reopened";
  opportunities?: ExitInterviewsListOpportunitiesParams;
}) {
  const { user } = usePortalSession();
  const access = getExitInterviewAccess(user);

  if (access.isStudent && access.canViewSelf) {
    return (
      <div className={pageSheetWidth}>
        <ExitInterviewStudentHome access={access} />
      </div>
    );
  }

  if (access.hasOperationalWorkspace) {
    const showingOpportunities = access.canManageOpportunities && (opportunities !== undefined || !access.canViewOperational);
    return <>
      {access.canViewOperational && access.canManageOpportunities ? <WorkspaceTabs label="Exit Interview navigation">
        <Link href="/portal/exit-interviews" aria-current={!showingOpportunities ? "page" : undefined} className={workspaceTabClass(!showingOpportunities)}>Responses</Link>
        <Link href="/portal/exit-interviews?workspace=opportunities" aria-current={showingOpportunities ? "page" : undefined} className={workspaceTabClass(showingOpportunities)}>Student access</Link>
      </WorkspaceTabs> : null}
      {showingOpportunities ? <ExitInterviewOpportunitiesPage filters={opportunities ?? {}} /> : <ExitInterviewOperationalList filters={filters} notice={notice} />}
    </>;
  }

  return <ExitInterviewUnavailable title="Exit Interview unavailable" />;
}

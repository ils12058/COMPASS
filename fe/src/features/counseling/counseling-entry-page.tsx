"use client";

import { ShieldCheck } from "lucide-react";

import { PageActionLink } from "@/components/ui/page-action";
import { pageSheetWidth } from "@/components/ui/page-width";
import { CounselorCases } from "@/features/counseling/cases/counselor-cases";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { CounselingPageHeading, CounselingUnavailable } from "@/features/counseling/counseling-shared";
import { StudentSessionSummaries } from "@/features/counseling/student-session-summaries";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function CounselingEntryPage() {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);

  // A Counselor's Counseling starts from their cases; sessions are part of each case.
  if (access.canViewAssigned) return <CounselorCases access={access} />;
  // Staff whose only Counseling access is case coverage reach it from here, as before.
  if (access.canViewCoverage) {
    return (
      <CounselingPageHeading
        title="Counseling"
        action={<PageActionLink href="/portal/counseling/coverage" icon={ShieldCheck} label="Case coverage" />}
      />
    );
  }
  if (access.isStudent && access.hasStudentWorkspace) {
    return (
      <div className={pageSheetWidth}>
        <StudentSessionSummaries access={access} />
      </div>
    );
  }
  return <CounselingUnavailable />;
}

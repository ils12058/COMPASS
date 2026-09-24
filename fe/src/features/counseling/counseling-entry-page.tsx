"use client";

import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { CounselingUnavailable } from "@/features/counseling/counseling-shared";
import { CounselorEncounters } from "@/features/counseling/counselor-encounters";
import { StudentSharedSummaries } from "@/features/counseling/student-shared-summaries";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function CounselingEntryPage() {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);

  if (access.isCounselor && access.hasCounselorWorkspace) return <CounselorEncounters access={access} />;
  if (access.isStudent && access.hasStudentWorkspace) return <StudentSharedSummaries access={access} />;
  return <CounselingUnavailable />;
}

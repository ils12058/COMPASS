"use client";

import { usePortalSession } from "@/features/portal/components/portal-session";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { CounselorRoutineWorkspace } from "@/features/routine-interviews/routine-counselor-workspace";
import { RoutineUnavailable } from "@/features/routine-interviews/routine-interviews-shared";
import { StudentRoutineWorkspace } from "@/features/routine-interviews/routine-student-workspace";

export function RoutineInterviewsEntryPage() {
  const { user } = usePortalSession();
  const access = getRoutineInterviewAccess(user);

  if (access.canViewSelf || (access.isStudent && access.canManageSelf)) {
    return <StudentRoutineWorkspace access={access} />;
  }
  if (access.isCounselor && (access.canViewAssigned || access.canManageAssigned)) {
    return <CounselorRoutineWorkspace access={access} />;
  }
  return <RoutineUnavailable />;
}
